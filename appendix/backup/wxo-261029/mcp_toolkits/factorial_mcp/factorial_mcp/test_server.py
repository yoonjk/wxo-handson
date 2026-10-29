"""Unit tests for the Factorial MCP Server (section-05/lab01/server.py).

Covers:
- _compute_factorial helper (happy path + error path)
- factorial_value tool (return type, correctness)
- factorial_digits tool (return type, correctness)
- Edge cases: 0!, 1!, large n
- MCP server registration: both tools are present
"""

import asyncio
import math
import os
import sys

import pytest

# Ensure the lab directory is on the path regardless of working directory
sys.path.insert(0, os.path.dirname(__file__))

from server import _compute_factorial, factorial_value, factorial_digits, mcp


# ---------------------------------------------------------------------------
# Helper: _compute_factorial
# ---------------------------------------------------------------------------

class TestComputeFactorial:
    def test_zero(self):
        assert _compute_factorial(0) == 1

    def test_one(self):
        assert _compute_factorial(1) == 1

    def test_small(self):
        assert _compute_factorial(5) == 120

    def test_ten(self):
        assert _compute_factorial(10) == 3628800

    def test_large(self):
        assert _compute_factorial(20) == math.factorial(20)

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            _compute_factorial(-1)

    def test_negative_large_raises(self):
        with pytest.raises(ValueError):
            _compute_factorial(-100)


# ---------------------------------------------------------------------------
# Tool: factorial_value
# ---------------------------------------------------------------------------

class TestFactorialValue:
    def test_returns_string(self):
        result = factorial_value(5)
        assert isinstance(result, str)

    def test_zero(self):
        assert factorial_value(0) == "1"

    def test_one(self):
        assert factorial_value(1) == "1"

    def test_five(self):
        assert factorial_value(5) == "120"

    def test_ten(self):
        assert factorial_value(10) == "3628800"

    def test_large_n(self):
        # 100! is a well-known number; verify leading digits
        result = factorial_value(100)
        assert isinstance(result, str)
        assert result.startswith("933262154439441526816992388562667")

    def test_negative_propagates_error(self):
        with pytest.raises(ValueError):
            factorial_value(-1)


# ---------------------------------------------------------------------------
# Tool: factorial_digits
# ---------------------------------------------------------------------------

class TestFactorialDigits:
    def test_returns_int(self):
        result = factorial_digits(5)
        assert isinstance(result, int)

    def test_zero(self):
        # 0! = 1  →  1 digit
        assert factorial_digits(0) == 1

    def test_one(self):
        # 1! = 1  →  1 digit
        assert factorial_digits(1) == 1

    def test_five(self):
        # 5! = 120  →  3 digits
        assert factorial_digits(5) == 3

    def test_ten(self):
        # 10! = 3628800  →  7 digits
        assert factorial_digits(10) == 7

    def test_large_n(self):
        # 100! has 158 digits
        assert factorial_digits(100) == 158

    def test_consistency_with_factorial_value(self):
        for n in [0, 1, 5, 15, 50]:
            assert factorial_digits(n) == len(factorial_value(n))

    def test_negative_propagates_error(self):
        with pytest.raises(ValueError):
            factorial_digits(-1)


# ---------------------------------------------------------------------------
# MCP server registration
# ---------------------------------------------------------------------------

def _tool_names() -> set[str]:
    """Return the set of registered tool names via the async FastMCP v4 API."""
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


class TestMCPServerRegistration:
    def test_server_name(self):
        assert mcp.name == "Factorial MCP Server"

    def test_tools_registered(self):
        """Both tools must be discoverable via the FastMCP tool registry."""
        names = _tool_names()
        assert "factorial_value" in names, "factorial_value tool not registered"
        assert "factorial_digits" in names, "factorial_digits tool not registered"

    def test_tool_count(self):
        assert len(_tool_names()) == 2
