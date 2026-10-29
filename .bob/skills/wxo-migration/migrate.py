#!/usr/bin/env python3
"""
watsonx Orchestrate Asset Migration Script (ADK CLI)
Order: Connections -> Knowledge Bases -> Tools -> Controls -> Agents

Custom-only migration rules:
  Connections   : name == app_id  (marketplace apps have a different display name)
                  AND app_id does NOT end with '_ibm_184bdbd3' (built-in system connections)
                  AND app_id is not 'WXO_PLATFORM_USER_API' (platform-provided connection)
  MCP Toolkits  : all included  (always user-created; exported as ZIP via `orchestrate toolkits export`)
  Tools         : toolkit_id is null  (marketplace toolkit tools are excluded)
  Knowledge Bases: all included  (always user-created)
  Controls      : all included
  Agents        : kind == 'native'  (platform default agents excluded)

Migration order: Connections -> MCP Toolkits -> Knowledge Bases -> Tools -> Controls -> Agents
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


def run_cmd(cmd: list[str], env: dict = None, check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Execute a CLI command with environment variables and return CompletedProcess."""
    current_env = os.environ.copy()
    if env:
        current_env.update(env)
    
    result = subprocess.run(
        cmd,
        env=current_env,
        text=True,
        capture_output=capture_output,
        check=False
    )
    if check and result.returncode != 0:
        cmd_str = " ".join(cmd)
        err_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
        print(f"❌ Command failed [{result.returncode}]: {cmd_str}\n{err_msg}", file=sys.stderr)
    return result


def parse_json_output(output: str) -> list | dict:
    """Safely parse JSON output from orchestrate CLI -v commands."""
    import re as _re
    clean = output.strip()
    if not clean:
        return []
    # Strip ANSI escape codes (color/control sequences from CLI output)
    clean = _re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', clean)
    # Remove any remaining non-printable control characters except tab/newline/CR
    clean = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', clean)

    # If there's leading/trailing non-json logs, find the first [ or {
    start_bracket = clean.find('[')
    start_brace = clean.find('{')

    start_idx = -1
    if start_bracket != -1 and start_brace != -1:
        start_idx = min(start_bracket, start_brace)
    elif start_bracket != -1:
        start_idx = start_bracket
    elif start_brace != -1:
        start_idx = start_brace

    if start_idx != -1:
        clean = clean[start_idx:]

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # Retry with strict=False to tolerate embedded control characters in CLI output
    try:
        return json.loads(clean, strict=False)
    except json.JSONDecodeError:
        return []


def setup_env(env_name: str, url: str, api_key: str) -> dict:
    """Configure and activate orchestrate environment.

    Uses 'env activate -a' exclusively to avoid any interactive stdin prompts.
    If the named env doesn't exist, 'env activate' with -a will create it automatically.
    If the URL needs to be registered first, we pre-register via 'env add' piping Y via stdin.
    """
    env_vars = {"WO_API_KEY": api_key, "WXO_INSTANCE_URL": url, "_ENV_NAME": env_name}
    print(f"⚙️  Configuring environment '{env_name}' -> {url}")

    # Check if env already exists
    list_res = run_cmd(["orchestrate", "env", "list"], env=env_vars, check=False)
    if env_name not in (list_res.stdout or ""):
        # Register the env using 'env add' — pipe "Y\n" to answer the update prompt silently
        import subprocess as _sp
        current_env = {**env_vars, **dict(os.environ)}
        _sp.run(
            ["orchestrate", "env", "add", "-n", env_name, "-u", url, "--activate"],
            input="Y\n",
            text=True,
            capture_output=True,
            env=current_env,
        )

    # Always activate with -a to set API key non-interactively
    # --skip-version-check avoids slow PyPI network calls that can block in CI/background
    run_cmd(["orchestrate", "env", "activate", env_name, "-a", api_key, "--skip-version-check"], env=env_vars, check=False)

    return env_vars


# ---------------------------------------------------------------------------
# Custom asset filters
# ---------------------------------------------------------------------------

PLATFORM_CONNECTIONS = {"WXO_PLATFORM_USER_API"}


def is_custom_connection(item: dict) -> bool:
    """
    A connection is considered custom when:
    1. Its display name equals its app_id  (marketplace apps have a distinct name)
    2. Its app_id does NOT end with '_ibm_184bdbd3'  (built-in system connections)
    3. Its app_id is not a platform-provided connection (e.g. WXO_PLATFORM_USER_API)
    """
    app_id = item.get("app_id", "")
    name = item.get("name", "")
    if app_id.endswith("_ibm_184bdbd3") or app_id in PLATFORM_CONNECTIONS:
        return False
    return name == app_id


def is_custom_tool(item: dict) -> bool:
    """A tool is custom when toolkit_id is null (not from a marketplace toolkit)."""
    return item.get("toolkit_id") is None


def is_custom_agent(item: dict) -> bool:
    """Only migrate native agents (user-created); skip platform-managed kinds."""
    return item.get("kind", "native") == "native"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_assets(backup_dir: Path, source_env: dict) -> dict:
    """Export CUSTOM-ONLY assets from source instance.

    Order:
      [1] Connections  (sequential — dependency base)
      [2] MCP Toolkits (sequential)
      [3] Tools ‖ Knowledge Bases ‖ Agents  (all three in parallel, no order dependency)
      [4] Controls     (sequential)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    stats = {"connections": 0, "mcp_toolkits": 0, "knowledge_bases": 0, "tools": 0, "controls": 0, "agents": 0}

    conn_dir     = backup_dir / "connections"
    toolkits_dir = backup_dir / "mcp_toolkits"
    kb_dir       = backup_dir / "knowledge_bases"
    tools_dir    = backup_dir / "tools"
    controls_dir = backup_dir / "controls"
    agents_dir   = backup_dir / "agents"

    for d in [conn_dir, toolkits_dir, kb_dir, tools_dir, controls_dir, agents_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── [1] Connections ──────────────────────────────────────────────────────
    print("\n================== [1] Exporting Connections (custom only) ==================")
    res = run_cmd(["orchestrate", "connections", "list", "-v"], env=source_env, check=False)
    conn_data = parse_json_output(res.stdout) if res.returncode == 0 else []

    seen_conn: set[str] = set()
    if isinstance(conn_data, list):
        for item in conn_data:
            app_id = item.get("app_id") or item.get("name") or item.get("id")
            if not app_id or app_id in seen_conn:
                continue
            if not is_custom_connection(item):
                print(f"  ⏭  Skipping system/marketplace connection: {app_id}")
                continue
            seen_conn.add(app_id)
            out_file = conn_dir / f"{app_id}.yaml"
            print(f"  → Exporting connection: {app_id}")
            exp = run_cmd(
                ["orchestrate", "connections", "export", "-a", app_id, "-o", str(out_file)],
                env=source_env, check=False,
            )
            if exp.returncode == 0:
                stats["connections"] += 1

    # ── [2] MCP Toolkits ─────────────────────────────────────────────────────
    print("\n================== [2] Exporting MCP Toolkits ==================")
    res = run_cmd(["orchestrate", "toolkits", "list", "-v"], env=source_env, check=False)
    toolkit_data = parse_json_output(res.stdout) if res.returncode == 0 else []

    if isinstance(toolkit_data, list):
        for item in toolkit_data:
            tk_name = item.get("name") or item.get("id")
            if tk_name:
                out_file = toolkits_dir / f"{tk_name}.zip"
                print(f"  → Exporting MCP toolkit: {tk_name}")
                exp = run_cmd(
                    ["orchestrate", "toolkits", "export", "-n", tk_name, "-o", str(out_file)],
                    env=source_env, check=False,
                )
                if exp.returncode == 0:
                    stats["mcp_toolkits"] += 1

    # ── [3] Tools ‖ KB ‖ Agents ‖ Controls  (parallel — no order dependency) ──
    print("\n====== [3] Exporting Tools ‖ Knowledge Bases ‖ Agents ‖ Controls (parallel) ======")

    # -- collect all lists first (fast sequential) --
    res_tools    = run_cmd(["orchestrate", "tools", "list", "-v"],           env=source_env, check=False)
    res_kb       = run_cmd(["orchestrate", "knowledge-bases", "list", "-v"], env=source_env, check=False)
    res_agents   = run_cmd(["orchestrate", "agents", "list", "-v"],          env=source_env, check=False)
    res_controls = run_cmd(["orchestrate", "controls", "list", "-v"],        env=source_env, check=False)

    tool_data     = parse_json_output(res_tools.stdout)    if res_tools.returncode    == 0 else []
    kb_data       = parse_json_output(res_kb.stdout)       if res_kb.returncode       == 0 else []
    agent_data    = parse_json_output(res_agents.stdout)   if res_agents.returncode   == 0 else []
    control_data  = parse_json_output(res_controls.stdout) if res_controls.returncode == 0 else []

    # agents list fallback to REST if CLI fails
    if not isinstance(agent_data, list) or not agent_data:
        print("  ⚠  'orchestrate agents list -v' failed — falling back to REST API")
        agent_data = _fetch_agents_via_rest(source_env)

    # Build unified task list: (kind_str, callable)
    tasks = []

    # Tools
    if isinstance(tool_data, list):
        for i in tool_data:
            if (i.get("name") or i.get("id")) and not is_custom_tool(i):
                print(f"  ⏭  Skipping marketplace tool: {i.get('name')} (toolkit_id={i.get('toolkit_id')})")
        custom_tools = [i for i in tool_data if (i.get("name") or i.get("id")) and is_custom_tool(i)]
        for item in custom_tools:
            tool_name = item.get("name") or item.get("id")
            out_file  = tools_dir / f"{tool_name}.zip"
            def _mk_tool(n=tool_name, f=out_file):
                def _run():
                    print(f"  → [tool] Exporting {n}")
                    res = run_cmd(
                        ["orchestrate", "tools", "export", "-n", n, "-o", str(f)],
                        env=source_env, check=False,
                    )
                    if res.returncode != 0:
                        return False
                    # Detect artifact-missing warnings — export "succeeds" but ZIP is empty/absent
                    combined = (res.stdout or "") + (res.stderr or "")
                    if "Could not find tool artifacts" in combined or \
                       "could not find uploaded" in combined.lower():
                        print(f"  ⚠  [tool] {n}: artifact missing in source — skipped")
                        if f.exists():
                            f.unlink()
                        return False
                    return True
                return _run
            tasks.append(("tool", _mk_tool()))

    # Knowledge Bases
    if isinstance(kb_data, list):
        for item in kb_data:
            kb_name  = item.get("name") or item.get("id")
            if not kb_name:
                continue
            out_file = kb_dir / f"{kb_name}.yaml"
            def _mk_kb(n=kb_name, f=out_file):
                def _run():
                    print(f"  → [kb]   Exporting {n}")
                    return run_cmd(
                        ["orchestrate", "knowledge-bases", "export", "-n", n, "-o", str(f)],
                        env=source_env, check=False,
                    ).returncode == 0
                return _run
            tasks.append(("kb", _mk_kb()))

    # Controls
    if isinstance(control_data, list):
        for item in control_data:
            ctrl_name = item.get("name") or item.get("id")
            if not ctrl_name:
                continue
            out_file = controls_dir / f"{ctrl_name}.yaml"
            def _mk_ctrl(n=ctrl_name, f=out_file):
                def _run():
                    print(f"  → [ctrl] Exporting {n}")
                    return run_cmd(
                        ["orchestrate", "controls", "export", "-n", n, "-o", str(f)],
                        env=source_env, check=False,
                    ).returncode == 0
                return _run
            tasks.append(("control", _mk_ctrl()))

    # Agents
    if isinstance(agent_data, list):
        for i in agent_data:
            if (i.get("name") or i.get("id")) and not is_custom_agent(i):
                print(f"  ⏭  Skipping non-native agent: {i.get('name')} (kind={i.get('kind','native')})")
        custom_agents = [i for i in agent_data if (i.get("name") or i.get("id")) and is_custom_agent(i)]
        for item in custom_agents:
            agent_name = item.get("name") or item.get("id")
            kind       = item.get("kind", "native")
            out_file   = agents_dir / f"{agent_name}.yaml"
            def _mk_agent(n=agent_name, k=kind, f=out_file):
                def _run():
                    print(f"  → [agent] Exporting {n} (kind: {k})")
                    exp = run_cmd(
                        ["orchestrate", "agents", "export", "-n", n, "-k", k,
                         "-o", str(f), "--agent-only"],
                        env=source_env, check=False,
                    )
                    if exp.returncode == 0:
                        return True
                    # Try alternate kinds as fallback
                    for fk in ("native", "external", "assistant"):
                        if fk == k:
                            continue
                        exp2 = run_cmd(
                            ["orchestrate", "agents", "export", "-n", n, "-k", fk,
                             "-o", str(f), "--agent-only"],
                            env=source_env, check=False,
                        )
                        if exp2.returncode == 0:
                            print(f"    ✓ {n} succeeded with kind={fk}")
                            return True
                    return False
                return _run
            tasks.append(("agent", _mk_agent()))

    # Run all 4 types (tools ‖ kb ‖ controls ‖ agents) in parallel (max 5 workers)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fn): kind for kind, fn in tasks}
        for future in as_completed(futures):
            kind = futures[future]
            try:
                ok = future.result()
            except Exception as exc:
                print(f"  ⚠  Task ({kind}) raised: {exc}")
                ok = False
            if ok:
                if kind == "tool":      stats["tools"] += 1
                elif kind == "kb":      stats["knowledge_bases"] += 1
                elif kind == "control": stats["controls"] += 1
                elif kind == "agent":   stats["agents"] += 1

    return stats


def _fetch_agents_via_rest(source_env: dict) -> list:
    """
    Retrieve agent list from WXO REST API when 'orchestrate agents list' fails.
    Reads WXO_INSTANCE_URL and WO_API_KEY from the env dict set by setup_env().
    """
    api_key = source_env.get("WO_API_KEY", "")
    if not api_key:
        print("  ⚠  WO_API_KEY not set — cannot call REST API")
        return []

    wxo_url = source_env.get("WXO_INSTANCE_URL", "")
    if not wxo_url:
        print("  ⚠  WXO_INSTANCE_URL not set — cannot call REST API")
        return []

    # Get IAM token — use requests (bundled with orchestrate ADK) with SSL verify disabled
    # as a fallback for macOS environments missing local issuer certificates.
    try:
        import requests as _requests
        resp = _requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        iam_token = resp.json()["access_token"]
    except Exception:
        # Final fallback: urllib with SSL verification disabled
        try:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            iam_body = f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}".encode()
            req = urllib.request.Request(
                "https://iam.cloud.ibm.com/identity/token",
                data=iam_body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                iam_token = json.loads(r.read())["access_token"]
        except Exception as e:
            print(f"  ⚠  Failed to get IAM token: {e}")
            return []

    # Call /v1/orchestrate/agents
    try:
        import requests as _requests
        agents_url = f"{wxo_url.rstrip('/')}/v1/orchestrate/agents"
        resp = _requests.get(
            agents_url,
            headers={"Authorization": f"Bearer {iam_token}", "Content-Type": "application/json"},
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        agents = resp.json()
        print(f"  ✓ REST API returned {len(agents)} agents")
        # Normalise: REST response has no 'kind', default to 'native'
        for a in agents:
            if "kind" not in a or not a["kind"]:
                a["kind"] = "native"
        return agents
    except Exception as e:
        print(f"  ⚠  REST API call failed: {e}")
        return []


def _import_tool(tool_name: str, extract_dir: Path, zip_path: Path, target_env: dict) -> bool:
    """
    Import a single tool into the target instance.

    Detection priority:
      1. Python  — binding.python in tool-spec.json  OR  .py files present with no openapi/flow files
                   → --kind python --file <module>.py --package-root <dir>
      2. OpenAPI — openapi*.json / openapi*.yaml / *.yaml containing 'openapi'/'swagger' keyword
                   → --kind openapi --file <spec>
      3. Flow    — *.json (not tool-spec.json) with no openapi/swagger content
                   → direct ADK API call (bypasses CLI bug where model=null)
    """
    spec_file = extract_dir / "tool-spec.json"
    binding = {}
    if spec_file.exists():
        try:
            binding = json.loads(spec_file.read_text(errors="ignore")).get("binding", {})
        except Exception:
            pass

    _HELPER_PY = {"db.py", "mysql_connection.py", "banking_db.py"}

    def _try_python_import(extract_dir: Path, func_ref: str = "", app_ids: list = None) -> bool:
        """Attempt to import a Python tool; returns True on success."""
        module_name = func_ref.split(":")[0] if ":" in func_ref else ""
        main_py = (extract_dir / f"{module_name}.py") if module_name else None
        if not main_py or not main_py.exists():
            candidates = [p for p in extract_dir.glob("*.py") if p.name not in _HELPER_PY]
            main_py = candidates[0] if candidates else next(iter(extract_dir.glob("*.py")), None)
        if not main_py or not main_py.exists():
            print(f"  ⚠ No main Python file found for {tool_name}")
            return False
        req_file = extract_dir / "requirements.txt"
        cmd = ["orchestrate", "tools", "import", "-k", "python",
               "-f", str(main_py), "--package-root", str(extract_dir)]
        if req_file.exists():
            cmd += ["--requirements-file", str(req_file)]
        # Add --app-id flags for each required connection
        for aid in (app_ids or []):
            cmd += ["--app-id", aid]
        app_str = f" app-ids={app_ids}" if app_ids else ""
        print(f"  → Importing Python tool: {tool_name} ({main_py.name}{app_str})")
        res = run_cmd(cmd, env=target_env, check=False)
        if res.returncode == 0:
            return True
        print(f"    ⚠ Failed: {(res.stderr or res.stdout or '').strip()[:200]}")
        return False

    # ── 1. Python tool (explicit binding) ─────────────────────────────────
    if "python" in binding:
        py_binding = binding["python"]
        func_ref = py_binding.get("function", "")
        # connections dict keys are the app_ids required by this tool
        app_ids = list((py_binding.get("connections") or {}).keys())
        return _try_python_import(extract_dir, func_ref, app_ids=app_ids)

    # ── 2. OpenAPI tool ────────────────────────────────────────────────────
    openapi_candidates = (
        list(extract_dir.glob("openapi*.json")) +
        list(extract_dir.glob("openapi*.yaml")) +
        list(extract_dir.glob("*.yaml"))
    )
    for candidate in openapi_candidates:
        content = candidate.read_text(errors="ignore")
        if "openapi" in content or "swagger" in content:
            print(f"  → Importing OpenAPI tool: {tool_name} ({candidate.name})")
            res = run_cmd(["orchestrate", "tools", "import", "-k", "openapi",
                           "-f", str(candidate)], env=target_env, check=False)
            if res.returncode == 0:
                return True
            print(f"    ⚠ Failed: {(res.stderr or res.stdout or '').strip()[:200]}")
            return False

    # ── 3. Flow tool ───────────────────────────────────────────────────────
    # ADK 2.17 import_flow_tool() requires model["spec"]["name"] but older
    # exports omit the "spec" wrapper. Fix: read JSON from the original ZIP,
    # inject "spec" if missing, write to a temp file, then call CLI import.
    if zip_path and zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path) as zf:
                json_members = [m for m in zf.namelist() if m.lstrip("/").endswith(".json")]
                if json_members:
                    raw = json.loads(zf.read(json_members[0]))
                    # Flow JSON: has "spec" or "steps" key, and no "openapi"/"paths"
                    is_flow = ("spec" in raw or "steps" in raw) and "paths" not in raw and "openapi" not in raw
                    if is_flow:
                        if "spec" not in raw:
                            raw["spec"] = {
                                "name": tool_name,
                                "display_name": raw.get("name", tool_name),
                                "description": raw.get("name", tool_name),
                            }
                        import tempfile as _tf, os as _os
                        with _tf.NamedTemporaryFile(
                            suffix=".json", delete=False, mode="w", encoding="utf-8"
                        ) as tmp:
                            json.dump(raw, tmp, ensure_ascii=False)
                            tmp_path = tmp.name
                        steps_n = len(raw.get("steps", []))
                        print(f"  → Importing Flow tool: {tool_name} (steps={steps_n})")
                        res = run_cmd(
                            ["orchestrate", "tools", "import", "-k", "flow", "-f", tmp_path],
                            env=target_env, check=False,
                        )
                        _os.unlink(tmp_path)
                        if res.returncode == 0:
                            return True
                        print(f"    ⚠ Failed: {(res.stderr or res.stdout or '').strip()[:300]}")
                        return False
        except Exception as e:
            print(f"    ⚠ Flow zip processing error: {e}")

    # Fallback: JSON already extracted in extract_dir
    for candidate in sorted(extract_dir.glob("*.json")):
        if candidate.name == "tool-spec.json":
            continue
        try:
            data = json.loads(candidate.read_text(errors="ignore"))
        except Exception:
            continue
        if "paths" in data or "openapi" in data:
            continue
        if "spec" not in data and "steps" not in data:
            continue
        if "spec" not in data:
            data["spec"] = {
                "name": tool_name,
                "display_name": data.get("name", tool_name),
                "description": data.get("name", tool_name),
            }
        import tempfile as _tf, os as _os
        with _tf.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False)
            tmp_path = tmp.name
        print(f"  → Importing Flow tool: {tool_name} ({candidate.name}, spec injected)")
        res = run_cmd(
            ["orchestrate", "tools", "import", "-k", "flow", "-f", tmp_path],
            env=target_env, check=False,
        )
        _os.unlink(tmp_path)
        if res.returncode == 0:
            return True
        print(f"    ⚠ Failed: {(res.stderr or res.stdout or '').strip()[:300]}")
        return False

    # ── 4. Python fallback (no spec, only .py files present) ──────────────
    py_files = [p for p in extract_dir.glob("*.py") if p.name not in _HELPER_PY]
    if py_files:
        print(f"  → Importing Python tool (no spec): {tool_name}")
        return _try_python_import(extract_dir)

    # ── MCP tool (toolkit-backed) ──────────────────────────────────────────
    # MCP tools belong to a toolkit; handled by the toolkits import step.
    print(f"  ⏭  Skipping {tool_name}: no importable spec found (may be MCP/toolkit-backed)")
    return False


def import_assets(backup_dir: Path, target_env: dict) -> dict:
    """Import all assets into target instance in strict order."""
    stats = {"connections": 0, "mcp_toolkits": 0, "knowledge_bases": 0, "tools": 0, "controls": 0, "agents": 0}

    conn_dir = backup_dir / "connections"
    toolkits_dir = backup_dir / "mcp_toolkits"
    kb_dir = backup_dir / "knowledge_bases"
    tools_dir = backup_dir / "tools"
    controls_dir = backup_dir / "controls"
    agents_dir = backup_dir / "agents"

    print("\n================== [1/6] Importing Connections ==================")
    if conn_dir.exists():
        for yaml_file in sorted(conn_dir.glob("*.yaml")):
            print(f"  → Importing connection: {yaml_file.name}")
            imp = run_cmd(["orchestrate", "connections", "import", "-f", str(yaml_file)], env=target_env, check=False)
            if imp.returncode == 0:
                stats["connections"] += 1

    print("\n================== [2/6] Importing MCP Toolkits ==================")
    if toolkits_dir.exists():
        for zip_path in sorted(toolkits_dir.glob("*.zip")):
            tk_name = zip_path.stem
            extract_dir = toolkits_dir / tk_name
            extract_dir.mkdir(exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                yaml_files = list(extract_dir.glob("*.yaml")) + list(extract_dir.glob("*.yml"))
                if not yaml_files:
                    print(f"  ⚠ No YAML spec found in {zip_path.name}")
                    continue

                spec_file = yaml_files[0]

                # Read spec to get package_root and resolve code directory.
                # orchestrate toolkits export only saves the YAML — not the server code.
                # The package_root in the spec must point to an existing directory
                # containing the actual server files (e.g. math_server.py).
                # Strategy: search workspace for a directory named <package_root>
                # that contains the command's entrypoint file.
                try:
                    import yaml as _yaml
                    spec_data = _yaml.safe_load(spec_file.read_text())
                    pkg_root_name = spec_data.get("package_root", tk_name)
                    command_file = spec_data.get("command", "").split()[-1] if spec_data.get("command") else ""

                    # Search workspace root (two levels up from backup_dir) for code dir
                    workspace = backup_dir.parent.parent
                    code_dir = None
                    for candidate in workspace.rglob(command_file or "*.py"):
                        if candidate.parent.name == pkg_root_name or \
                           (command_file and candidate.name == command_file and
                                candidate.parent.name not in ("__pycache__", ".venv")):
                            if ".venv" not in str(candidate):
                                code_dir = candidate.parent
                                break

                    if code_dir and code_dir.exists():
                        # Rewrite package_root in spec to absolute path
                        spec_data["package_root"] = str(code_dir)
                        import tempfile
                        tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w")
                        _yaml.dump(spec_data, tmp)
                        tmp.close()
                        import_spec = Path(tmp.name)
                        print(f"  → Importing MCP toolkit: {tk_name} (code: {code_dir})")
                    else:
                        import_spec = spec_file
                        print(f"  → Importing MCP toolkit: {tk_name} (spec only — code not found locally)")
                except Exception:
                    import_spec = spec_file
                    print(f"  → Importing MCP toolkit: {tk_name} (spec: {spec_file.name})")

                imp = run_cmd(
                    ["orchestrate", "toolkits", "import", "-f", str(import_spec)],
                    env=target_env, check=False,
                )
                if imp.returncode == 0:
                    stats["mcp_toolkits"] += 1
                else:
                    err = (imp.stdout or imp.stderr or "").strip()
                    # Already exists → count as success (idempotent re-import)
                    if "Existing MCP toolkit found" in err or "already exists" in err.lower():
                        print(f"  ✅ Toolkit {tk_name} already exists — skipped")
                        stats["mcp_toolkits"] += 1
                    else:
                        print(f"  ⚠ Failed to import toolkit {tk_name}: {err[:120]}")
            except Exception as e:
                print(f"  ⚠ Failed to process toolkit zip {zip_path.name}: {e}")

    print("\n================ [3/6] Importing Knowledge Bases ================")
    if kb_dir.exists():
        import tempfile as _tf, yaml as _yaml

        # Prepare a tiny placeholder document for KBs that have no documents/index_config.
        # The ADK CLI rejects import if both documents and index_config are empty.
        _placeholder_txt = Path(_tf.mktemp(suffix=".txt"))
        _placeholder_txt.write_text("placeholder")

        for yaml_file in sorted(kb_dir.glob("*.yaml")):
            kb_name = yaml_file.stem
            print(f"  → Importing knowledge base: {kb_name}")

            # Check if KB already exists — skip if so (idempotent)
            chk = run_cmd(["orchestrate", "knowledge-bases", "status", "-n", kb_name],
                          env=target_env, check=False)
            if chk.returncode == 0:
                print(f"  ✅ KB '{kb_name}' already exists — skipped")
                stats["knowledge_bases"] += 1
                continue

            # Read spec to detect empty KB (no documents, no index_config)
            try:
                spec = _yaml.safe_load(yaml_file.read_text())
                has_docs = bool(spec.get("documents"))
                has_index = bool(
                    spec.get("conversational_search_tool", {}).get("index_config")
                )
                if not has_docs and not has_index:
                    # Inject placeholder document path so ADK accepts the import
                    tmp_spec = dict(spec)
                    tmp_spec["documents"] = [str(_placeholder_txt)]
                    # Remove connection-dependent index_config to avoid auth errors
                    if "conversational_search_tool" in tmp_spec:
                        tmp_spec["conversational_search_tool"] = dict(
                            tmp_spec["conversational_search_tool"]
                        )
                        tmp_spec["conversational_search_tool"]["index_config"] = []
                    tmp_yaml = Path(_tf.mktemp(suffix=".yaml"))
                    tmp_yaml.write_text(_yaml.dump(tmp_spec, allow_unicode=True))
                    import_file = tmp_yaml
                else:
                    import_file = yaml_file
            except Exception:
                import_file = yaml_file

            imp = run_cmd(
                ["orchestrate", "knowledge-bases", "import", "-f", str(import_file)],
                env=target_env, check=False,
            )
            if imp.returncode == 0:
                print(f"  ✅ KB '{kb_name}' imported successfully")
                stats["knowledge_bases"] += 1
            else:
                err = (imp.stderr or imp.stdout or "").strip()
                if "already exists" in err.lower() or "updated successfully" in err.lower():
                    print(f"  ✅ KB '{kb_name}' already exists — skipped")
                    stats["knowledge_bases"] += 1
                else:
                    print(f"  ⚠ Failed to import KB '{kb_name}': {err[:200]}")

        _placeholder_txt.unlink(missing_ok=True)

    print("\n==================== [4/6] Importing Tools (parallel, 5 workers) ===========")
    if tools_dir.exists():
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        zip_paths = sorted(tools_dir.glob("*.zip"))

        def _import_one_tool(zip_path: Path):
            tool_name = zip_path.stem
            extract_dir = tools_dir / tool_name
            extract_dir.mkdir(exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                return _import_tool(tool_name, extract_dir, zip_path, target_env)
            except Exception as e:
                print(f"  ⚠ Failed to process tool zip {zip_path.name}: {e}")
                return False

        _print_lock = threading.Lock()
        _orig_print = print

        def _safe_print(*args, **kwargs):
            with _print_lock:
                _orig_print(*args, **kwargs)

        # Use 5 parallel workers — enough to saturate WXO API without hammering it
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_import_one_tool, zp): zp.stem for zp in zip_paths}
            for future in as_completed(futures):
                if future.result():
                    stats["tools"] += 1

    print("\n=================== [5/6] Importing Controls ====================")
    if controls_dir.exists():
        for yaml_file in sorted(controls_dir.glob("*.yaml")):
            print(f"  → Importing control: {yaml_file.name}")
            imp = run_cmd(["orchestrate", "controls", "import", "-f", str(yaml_file)], env=target_env, check=False)
            if imp.returncode == 0:
                stats["controls"] += 1

    # Agents import starts AFTER all tools are fully imported (ThreadPoolExecutor above
    # is a context manager — it blocks here until all tool futures complete).
    print("\n==================== [6/6] Importing Agents (parallel, 5 workers — after tools complete) =========")
    if agents_dir.exists():
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _import_one_agent(yaml_file: Path):
            print(f"  → Importing agent: {yaml_file.name}")
            imp = run_cmd(["orchestrate", "agents", "import", "-f", str(yaml_file)], env=target_env, check=False)
            if imp.returncode == 0:
                return True
            err = (imp.stderr or imp.stdout or "").strip()
            print(f"    ⚠ Failed [{yaml_file.stem}]: {err[:300]}")
            return False

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_import_one_agent, yf): yf.stem
                       for yf in sorted(agents_dir.glob("*.yaml"))}
            for future in as_completed(futures):
                if future.result():
                    stats["agents"] += 1

    return stats


# ---------------------------------------------------------------------------
# Parity check
# ---------------------------------------------------------------------------

def _count_assets(env: dict) -> dict:
    """
    Count custom assets on an instance using the same filter rules as export.
    Returns dict: {connections, mcp_toolkits, knowledge_bases, tools, controls, agents}
    """
    counts = {"connections": 0, "mcp_toolkits": 0, "knowledge_bases": 0,
              "tools": 0, "controls": 0, "agents": 0}

    # Activate the correct env before querying (avoids cross-env contamination)
    env_name = env.get("_ENV_NAME", "")
    if env_name:
        run_cmd(["orchestrate", "env", "activate", env_name, "--skip-version-check"], env=env, check=False)

    # Connections — custom only
    res = run_cmd(["orchestrate", "connections", "list", "-v"], env=env, check=False)
    if res.returncode == 0:
        data = parse_json_output(res.stdout)
        if isinstance(data, list):
            seen: set[str] = set()
            for item in data:
                app_id = item.get("app_id", "")
                if app_id and app_id not in seen and is_custom_connection(item):
                    seen.add(app_id)
                    counts["connections"] += 1

    # MCP Toolkits — all user-created (exclude ootb)
    res = run_cmd(["orchestrate", "toolkits", "list", "-v"], env=env, check=False)
    data = parse_json_output(res.stdout) if res.returncode == 0 else []
    if not isinstance(data, list) or not data:
        # Fallback: strict=False for control chars in output
        try:
            import re as _re
            clean = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', res.stdout or "")
            m = _re.search(r'\[.*\]', clean, _re.DOTALL)
            data = json.loads(m.group(), strict=False) if m else []
        except Exception:
            data = []
    if isinstance(data, list):
        counts["mcp_toolkits"] = sum(
            1 for t in data if not t.get("name", "").startswith("wxo_ootb_")
        )

    # Knowledge Bases — all
    res = run_cmd(["orchestrate", "knowledge-bases", "list", "-v"], env=env, check=False)
    if res.returncode == 0:
        data = parse_json_output(res.stdout)
        counts["knowledge_bases"] = len(data) if isinstance(data, list) else 0

    # Tools — custom only (toolkit_id == null)
    res = run_cmd(["orchestrate", "tools", "list", "-v"], env=env, check=False)
    if res.returncode == 0:
        data = parse_json_output(res.stdout)
        if isinstance(data, list):
            counts["tools"] = sum(1 for t in data if is_custom_tool(t))

    # Controls — all
    res = run_cmd(["orchestrate", "controls", "list", "-v"], env=env, check=False)
    if res.returncode == 0:
        data = parse_json_output(res.stdout)
        counts["controls"] = len(data) if isinstance(data, list) else 0

    # Agents — native only; fallback to REST if CLI fails or returns empty
    res = run_cmd(["orchestrate", "agents", "list", "-v"], env=env, check=False)
    data = parse_json_output(res.stdout) if res.returncode == 0 else []
    if isinstance(data, list) and data:
        counts["agents"] = sum(1 for a in data if is_custom_agent(a))
    else:
        # CLI returned exit 0 but empty/invalid output (HTTP 500 server bug) — use REST
        agents = _fetch_agents_via_rest(env)
        counts["agents"] = sum(1 for a in agents if is_custom_agent(a))

    return counts


def check_parity(source_env: dict, target_env: dict) -> bool:
    """
    Compare custom asset counts between source and target.
    Prints a formatted table and returns True if all counts match.
    """
    print("\n" + "=" * 62)
    print("  🔍  Source ↔ Target Parity Check")
    print("=" * 62)
    print(f"  {'Asset':<20} {'Source':>8} {'Target':>8}  {'Status'}")
    print("-" * 62)

    print("  Counting source assets...")
    src = _count_assets(source_env)
    print("  Counting target assets...")
    tgt = _count_assets(target_env)

    all_match = True
    labels = {
        "connections":    "Connections",
        "mcp_toolkits":   "MCP Toolkits",
        "knowledge_bases":"Knowledge Bases",
        "tools":          "Tools",
        "controls":       "Controls",
        "agents":         "Agents",
    }
    for key, label in labels.items():
        s = src.get(key, 0)
        t = tgt.get(key, 0)
        if s == t:
            status = "✅ match"
        else:
            status = f"❌ mismatch  (diff: {t - s:+d})"
            all_match = False
        print(f"  {label:<20} {s:>8} {t:>8}  {status}")

    print("=" * 62)
    if all_match:
        print("  ✅ All asset counts match between source and target.")
    else:
        print("  ❌ Some asset counts differ. Review import logs above.")
    print("=" * 62 + "\n")
    return all_match


def main():
    from datetime import datetime
    today = datetime.now().strftime("%y%m%d")          # e.g. 261028
    default_source_env = f"wxo-source-{today}"
    default_target_env = f"wxo-{today}"

    parser = argparse.ArgumentParser(
        description="watsonx Orchestrate Asset Migration CLI (custom assets only)",
    )
    parser.add_argument("--source-url", required=True, help="Source watsonx Orchestrate instance URL")
    parser.add_argument("--source-key", required=True, help="Source instance API key")
    parser.add_argument("--target-url", required=True, help="Target watsonx Orchestrate instance URL")
    parser.add_argument("--target-key", required=True, help="Target instance API key")
    parser.add_argument("--backup-dir", default="./wxo_migration_backup", help="Directory to store exported assets")
    parser.add_argument("--stage", choices=["all", "export", "import", "verify"], default="all",
                        help="Migration stage: all | export | import | verify")
    parser.add_argument("--source-env-name", default=default_source_env,
                        help=f"Orchestrate env name for source (default: {default_source_env})")
    parser.add_argument("--target-env-name", default=default_target_env,
                        help=f"Orchestrate env name for target (default: {default_target_env})")

    args = parser.parse_args()
    backup_path = Path(args.backup_dir).resolve()

    print("🚀 Starting watsonx Orchestrate Migration")
    print(f"📁 Backup directory: {backup_path}")
    print(f"🏷️  Source env name : {args.source_env_name}")
    print(f"🏷️  Target env name : {args.target_env_name}")

    source_env = None
    target_env = None

    if args.stage in ["all", "export"]:
        source_env = setup_env(args.source_env_name, args.source_url, args.source_key)
        exp_stats = export_assets(backup_path, source_env)
        print("\n📊 Export Summary:")
        for k, v in exp_stats.items():
            print(f"   - {k.replace('_', ' ').capitalize()}: {v}")

    if args.stage in ["all", "import"]:
        target_env = setup_env(args.target_env_name, args.target_url, args.target_key)
        imp_stats = import_assets(backup_path, target_env)
        print("\n📊 Import Summary:")
        for k, v in imp_stats.items():
            print(f"   - {k.replace('_', ' ').capitalize()}: {v}")

    if args.stage in ["all", "verify"]:
        if source_env is None:
            source_env = setup_env(args.source_env_name, args.source_url, args.source_key)
        if target_env is None:
            target_env = setup_env(args.target_env_name, args.target_url, args.target_key)
        check_parity(source_env, target_env)

    print("\n✅ Migration process completed!")


if __name__ == "__main__":
    main()
