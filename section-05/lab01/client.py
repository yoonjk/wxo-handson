"""MCP client — connects to the Factorial MCP Server via stdio subprocess.

The client spawns server.py as a child process and communicates over
stdin/stdout using the MCP protocol (stdio transport).

Usage:
    python client.py
"""

import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

# ── Paths ─────────────────────────────────────────────────────────────────────

LAB_DIR    = Path(__file__).parent
SERVER     = LAB_DIR / "server.py"
PYTHON     = Path(sys.executable)          # .venv/bin/python
SEP        = "─" * 62


# ── Helpers ───────────────────────────────────────────────────────────────────

async def call(client: Client, tool: str, args: dict) -> str:
    result = await client.call_tool(tool, args)
    return result.content[0].text


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    transport = PythonStdioTransport(
        script_path=SERVER,
        python_cmd=str(PYTHON),
        cwd=str(LAB_DIR),
    )

    print(SEP)
    print("  Connecting to Factorial MCP Server  (stdio transport)")
    print(f"  server  : {SERVER}")
    print(f"  python  : {PYTHON}")
    print(SEP)

    async with Client(transport) as client:

        # ── 1. Server / tool discovery ────────────────────────────
        tools = await client.list_tools()
        print(f"\n  Connected ✓   Registered tools ({len(tools)}):")
        for t in tools:
            print(f"    • {t.name}")
            print(f"      {t.description.splitlines()[0]}")
        print()

        # ── 2. factorial_value ────────────────────────────────────
        print(SEP)
        print("  Tool ① : factorial_value(n)  →  exact n! as string")
        print(SEP)
        print(f"  {'n':>6}  result")
        print(f"  {'─'*6}  {'─'*50}")
        for n in [0, 1, 5, 10, 20, 50, 100]:
            value = await call(client, "factorial_value", {"n": n})
            display = value if len(value) <= 48 else value[:45] + "..."
            print(f"  {n:>6}  {display}")
        print()

        # ── 3. factorial_digits ───────────────────────────────────
        print(SEP)
        print("  Tool ② : factorial_digits(n)  →  digit count of n!")
        print(SEP)
        print(f"  {'n':>6}  {'digits':>10}")
        print(f"  {'─'*6}  {'─'*10}")
        for n in [0, 1, 5, 10, 20, 50, 100, 500, 1000]:
            digits = await call(client, "factorial_digits", {"n": n})
            print(f"  {n:>6}  {digits:>10}")
        print()

        # ── 4. Error handling ─────────────────────────────────────
        print(SEP)
        print("  Error handling : negative input")
        print(SEP)
        for tool, n in [("factorial_value", -1), ("factorial_digits", -5)]:
            try:
                await call(client, tool, {"n": n})
                print(f"  ✗ FAIL  {tool}({n}) — no exception raised")
            except Exception as exc:
                print(f"  ✓ PASS  {tool}({n}) raised: {exc}")
        print()

        print(SEP)
        print("  Session complete ✓")
        print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
