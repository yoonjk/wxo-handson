"""MCP client test suite for the Factorial MCP Server.

The client spawns server.py as a real subprocess and communicates over
stdin/stdout using the MCP protocol (stdio transport).
Every tool call travels through the full MCP protocol stack.

Usage:
    python client_test.py
"""

import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

LAB_DIR = Path(__file__).parent
SERVER  = LAB_DIR / "server.py"
PYTHON  = Path(sys.executable)      # .venv/bin/python

# ── Formatting helpers ────────────────────────────────────────────────────────

SEP  = "─" * 62
PASS = "✓ PASS"
FAIL = "✗ FAIL"

_results: list[tuple[str, bool, str]] = []   # (label, passed, detail)


def _record(label: str, passed: bool, detail: str = "") -> None:
    _results.append((label, passed, detail))
    status = PASS if passed else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  {status}  {label}{suffix}")


# ── Individual test helpers ───────────────────────────────────────────────────

async def check_factorial_value(client: Client, n: int, expected: str) -> None:
    result = await client.call_tool("factorial_value", {"n": n})
    got = result.content[0].text
    passed = got == expected
    _record(
        f"factorial_value({n}) == '{expected[:30]}{'...' if len(expected)>30 else ''}'",
        passed,
        f"got '{got[:30]}'" if not passed else "",
    )


async def check_factorial_digits(client: Client, n: int, expected: int) -> None:
    result = await client.call_tool("factorial_digits", {"n": n})
    got = int(result.content[0].text)
    passed = got == expected
    _record(
        f"factorial_digits({n}) == {expected}",
        passed,
        f"got {got}" if not passed else "",
    )


async def check_error(client: Client, tool: str, args: dict, match: str) -> None:
    label = f"{tool}({', '.join(f'{k}={v}' for k,v in args.items())}) raises ValueError"
    try:
        await client.call_tool(tool, args)
        _record(label, False, "no exception raised")
    except Exception as exc:
        passed = match in str(exc)
        _record(label, passed, "" if passed else f"unexpected message: {exc}")


async def check_return_type(client: Client, tool: str, n: int, expected_type: type) -> None:
    result = await client.call_tool(tool, {"n": n})
    raw = result.content[0].text
    try:
        expected_type(raw)          # str → str OK; int("3") → OK
        passed = True
    except (ValueError, TypeError):
        passed = False
    _record(
        f"{tool}({n}) returns {expected_type.__name__}",
        passed,
        f"raw value: '{raw}'" if not passed else "",
    )


async def check_consistency(client: Client, n: int) -> None:
    """factorial_digits(n) must equal len(factorial_value(n))."""
    r_val    = await client.call_tool("factorial_value",  {"n": n})
    r_digits = await client.call_tool("factorial_digits", {"n": n})
    val    = r_val.content[0].text
    digits = int(r_digits.content[0].text)
    passed = digits == len(val)
    _record(
        f"factorial_digits({n}) == len(factorial_value({n}))",
        passed,
        f"digits={digits}, len(value)={len(val)}" if not passed else "",
    )


# ── Main test runner ──────────────────────────────────────────────────────────

async def run() -> None:
    transport = PythonStdioTransport(
        script_path=SERVER,
        python_cmd=str(PYTHON),
        cwd=str(LAB_DIR),
    )

    async with Client(transport) as client:

        # ── Server info ───────────────────────────────────────────
        print(SEP)
        print("  MCP Server : Factorial MCP Server  (stdio transport)")
        print(f"  server : {SERVER}")
        print(SEP)

        # ── Tool discovery ────────────────────────────────────────
        tools = await client.list_tools()
        print(f"\n  Registered tools ({len(tools)}):")
        for t in tools:
            print(f"    • {t.name} — {t.description.splitlines()[0]}")
        print()

        # ═══════════════════════════════════════════════════════════
        # Test Group 1 — Return types
        # ═══════════════════════════════════════════════════════════
        print(SEP)
        print("  Test Group 1 : Return Types")
        print(SEP)
        await check_return_type(client, "factorial_value",  5, str)
        await check_return_type(client, "factorial_digits", 5, int)
        print()

        # ═══════════════════════════════════════════════════════════
        # Test Group 2 — factorial_value correctness
        # ═══════════════════════════════════════════════════════════
        print(SEP)
        print("  Test Group 2 : factorial_value(n) — exact values")
        print(SEP)
        cases_value = [
            (0,   "1"),
            (1,   "1"),
            (5,   "120"),
            (10,  "3628800"),
            (15,  "1307674368000"),
            (20,  "2432902008176640000"),
            # 100! — full exact value (158 digits)
            (100, "9332621544394415268169923885626670049071596826438162146859"
                  "2963895217599993229915608941463976156518286253697920827223"
                  "758251185210916864000000000000000000000000"),
        ]
        for n, expected in cases_value:
            await check_factorial_value(client, n, expected)
        print()

        # ═══════════════════════════════════════════════════════════
        # Test Group 3 — factorial_digits correctness
        # ═══════════════════════════════════════════════════════════
        print(SEP)
        print("  Test Group 3 : factorial_digits(n) — digit counts")
        print(SEP)
        cases_digits = [
            (0,    1),
            (1,    1),
            (5,    3),
            (10,   7),
            (15,  13),
            (20,  19),
            (100, 158),
            (500, 1135),
        ]
        for n, expected in cases_digits:
            await check_factorial_digits(client, n, expected)
        print()

        # ═══════════════════════════════════════════════════════════
        # Test Group 4 — Consistency between both tools
        # ═══════════════════════════════════════════════════════════
        print(SEP)
        print("  Test Group 4 : Consistency — digits == len(value)")
        print(SEP)
        for n in [0, 1, 5, 10, 50, 100]:
            await check_consistency(client, n)
        print()

        # ═══════════════════════════════════════════════════════════
        # Test Group 5 — Error handling (negative input)
        # ═══════════════════════════════════════════════════════════
        print(SEP)
        print("  Test Group 5 : Error Handling — negative input")
        print(SEP)
        await check_error(client, "factorial_value",  {"n": -1},  "non-negative")
        await check_error(client, "factorial_value",  {"n": -50}, "non-negative")
        await check_error(client, "factorial_digits", {"n": -1},  "non-negative")
        await check_error(client, "factorial_digits", {"n": -99}, "non-negative")
        print()

        # ── Summary ───────────────────────────────────────────────
        total  = len(_results)
        passed = sum(1 for _, ok, _ in _results if ok)
        failed = total - passed

        print(SEP)
        print(f"  Results : {passed}/{total} passed", end="")
        print("  ✓ All tests passed" if failed == 0 else f"  ✗ {failed} failed")
        print(SEP)

        if failed:
            print("\n  Failed tests:")
            for label, ok, detail in _results:
                if not ok:
                    print(f"    {FAIL}  {label}  ({detail})")
            print()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
