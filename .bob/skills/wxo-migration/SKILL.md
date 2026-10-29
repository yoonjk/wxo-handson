---
name: wxo-migration
description: Migrates watsonx Orchestrate custom assets (connections, MCP toolkits, knowledge bases, tools, controls, agents) between instances using the ADK CLI. Use when migrating or syncing watsonx Orchestrate environments, exporting/importing assets across instances with source and target URLs and API keys.
---

# watsonx Orchestrate Asset Migration Guide

This skill guides you through migrating **custom-developed** watsonx Orchestrate assets between instances using the Orchestrate ADK CLI (`orchestrate`).

## Custom-Only Migration Policy

Only assets directly created by users are migrated. Marketplace/platform-provided assets are automatically skipped.

| Asset Type | Custom Filter Rule | Skipped |
|---|---|---|
| **Connections** | `name == app_id` AND `app_id` does NOT end with `_ibm_184bdbd3` AND `app_id != WXO_PLATFORM_USER_API` | Marketplace apps, built-in system connections, and the platform-provided `WXO_PLATFORM_USER_API` |
| **MCP Toolkits** | All included — spec exported as ZIP, code auto-resolved from workspace | — (always user-created) |
| **Knowledge Bases** | All included | — (always user-created) |
| **Tools** | `toolkit_id == null` | Marketplace toolkit tools |
| **Controls** | All included | — |
| **Agents** | `kind == "native"` | Platform-managed agents (`external`, `assistant`) |

---

## Migration Sequence

### Export Order
```
[1] Connections     (sequential)
[2] MCP Toolkits    (sequential)
[3] Tools ‖ Knowledge Bases ‖ Agents   (ALL THREE in parallel, no order dependency)
[4] Controls        (sequential)
```

### Import Order
```
[1] Connections     (sequential)
[2] MCP Toolkits    (sequential)
[3] Knowledge Bases (sequential)
[4] Tools           (parallel, 5 workers)        ← must complete before agents
[5] Controls        (sequential)
[6] Agents          (parallel, 5 workers)        ← starts after [4] fully done
```

### Tool Type Detection (import)

| Priority | Condition | Import kind |
|---|---|---|
| 1 | `binding.python` in `tool-spec.json` | `python` + `--package-root` + `--app-id` (from `connections` dict) |
| 2 | `openapi*.json` / `*.yaml` containing `openapi`/`swagger` | `openapi` |
| 3 | `*.json` with `spec` or `steps` key (no `openapi`/`paths`) | `flow` (see ADK bug note below) |
| 4 | `.py` files only, no spec | `python` (fallback) |

> **⚠️ ADK 2.17 Flow Tool Bug**: `orchestrate tools import -k flow` reads `model["spec"]["name"]` but exported JSON from older instances has no `spec` wrapper → `KeyError: 'spec'`. Fix: the script reads the JSON from the original ZIP, injects a `spec` field if missing (`name = zip stem`, `description = flow name`), writes to a temp file, then calls CLI import.

> **⚠️ Python Tool `--app-id`**: Python tools that require a DB/API connection will fail without `--app-id`. The script automatically reads `binding.python.connections` keys from `tool-spec.json` and passes them as `--app-id` flags.

---

## Step 1: Gather Required User Inputs

Required parameters (ask with `ask_followup_question` if not provided):
- **Source Instance URL** (e.g. `https://api.us-south.watson-orchestrate.cloud.ibm.com/instances/<id>`)
- **Source API Key**
- **Target Instance URL**
- **Target API Key**
- **Backup Directory** (optional, default: `./appendix/backup/wxo-YYMMDD`)

---

## Step 2: Run Migration Script

```bash
# Full migration (export → import → verify)
python3 .bob/skills/wxo-migration/migrate.py \
  --source-url "<SOURCE_URL>" \
  --source-key "<SOURCE_API_KEY>" \
  --target-url "<TARGET_URL>" \
  --target-key "<TARGET_API_KEY>" \
  --backup-dir "./appendix/backup/wxo-YYMMDD"

# Export only
python3 .bob/skills/wxo-migration/migrate.py \
  --source-url "<SOURCE_URL>" --source-key "<KEY>" \
  --target-url "<TARGET_URL>" --target-key "<KEY>" \
  --backup-dir "./appendix/backup/wxo-YYMMDD" \
  --stage export

# Import only (from existing backup)
python3 .bob/skills/wxo-migration/migrate.py \
  --source-url "<SOURCE_URL>" --source-key "<KEY>" \
  --target-url "<TARGET_URL>" --target-key "<KEY>" \
  --backup-dir "./appendix/backup/wxo-YYMMDD" \
  --stage import

# Verify only (parity check)
python3 .bob/skills/wxo-migration/migrate.py \
  --source-url "<SOURCE_URL>" --source-key "<KEY>" \
  --target-url "<TARGET_URL>" --target-key "<KEY>" \
  --stage verify
```

### `--stage` options

| Value | Description |
|---|---|
| `all` (default) | export → import → verify |
| `export` | Export custom assets from source only |
| `import` | Import backed-up assets to target only |
| `verify` | Compare source ↔ target asset counts |

### Environment Naming

Auto-generated from today's date (`YYMMDD`):

| Role | Default name |
|---|---|
| Source | `wxo-source-YYMMDD` |
| Target | `wxo-YYMMDD` |

Override with `--source-env-name` / `--target-env-name`.

---

## Known Limitations

| Issue | Root Cause | Handled? |
|---|---|---|
| `orchestrate agents list -v` → HTTP 500 | Server bug: exit 0 but empty stdout | ✅ Empty output triggers REST API fallback |
| `orchestrate env activate` blocks (PyPI check) | Network call | ✅ `--skip-version-check` |
| Flow tool import → `KeyError: 'spec'` | ADK 2.17 export/import format mismatch | ✅ `spec` injected from ZIP |
| Flow tool model = null after import | ADK 2.17 CLI doesn't upload artifact for flow kind | ✅ `spec` injection triggers correct upload path |
| Python tool `--app-id` missing | `connections` dict in `tool-spec.json` not used | ✅ Auto-extracted from `binding.python.connections` |
| `orchestrate env add` stdin prompt | Interactive Y/N prompt | ✅ `input="Y\n"` via subprocess |
| CLI output JSON parse error | ANSI control chars + non-printable bytes in stdout | ✅ Strip ANSI + `strict=False` retry |
| `verify` shows 0 for KB/Tools/Agents | `_count_assets` called without re-activating correct env | ✅ `_count_assets` activates env before each query |
| `_fetch_agents_via_rest` calls wrong instance | Active env contamination — reads config file URL instead of env dict | ✅ `WXO_INSTANCE_URL` stored in env dict by `setup_env()` |
| Empty KB import fails | `documents: []` + `index_config: []` rejected by ADK | ✅ Placeholder `.txt` auto-injected; cleaned up after import |
| MCP Toolkit re-import fails | "Existing MCP toolkit found" error on idempotent import | ✅ Detected and counted as success (skip) |
| Tool export silently skipped | `Could not find tool artifacts` warning — artifact lost in source | ✅ Warning detected; file removed; logged as skipped |
| Agents fail: KB/tool not found | Dependency missing in target | ⚠️ Logged — re-run `--stage import` after dependency resolves |
| Tool artifact loss in source | Source instance data corruption — artifact never uploaded or deleted | ❌ Not recoverable — must re-upload tool in source UI |

---

## Relevant Files

```
.bob/skills/wxo-migration/
├── migrate.py     ← Migration script
└── SKILL.md       ← This file

appendix/backup/wxo-<YYMMDD>/
├── connections/   ← YAML files
├── mcp_toolkits/  ← ZIP files + extracted dirs
├── knowledge_bases/
├── tools/         ← ZIP files + extracted dirs
├── controls/
└── agents/        ← YAML files
```

## `migrate.py` Key Functions

| Function | Role |
|---|---|
| `setup_env()` | Register/activate orchestrate env; stores `WXO_INSTANCE_URL` + `_ENV_NAME` in env dict |
| `parse_json_output()` | Strip ANSI codes, `strict=False` retry — tolerates control chars in CLI stdout |
| `export_assets()` | 6-step parallel export; detects artifact-missing warnings and skips silently |
| `import_assets()` | 6-step import; KB placeholder injection, MCP Toolkit idempotent skip, Tools parallel |
| `_import_tool()` | Auto-detect Python/OpenAPI/Flow, inject `spec`, pass `--app-id` |
| `_fetch_agents_via_rest()` | REST fallback using `WXO_INSTANCE_URL` from env dict (not active config) |
| `_count_assets()` | Activates correct env before each query; REST fallback for agents |
| `check_parity()` | Source ↔ target asset count comparison table |
| `main()` | argparse: `--stage`, `--source/target-env-name` |

## Supporting files in this skill directory:
- migrate.py
- __pycache__/migrate.cpython-312.pyc

Use the read_file tool with paths relative to: .bob/skills/wxo-migration/
