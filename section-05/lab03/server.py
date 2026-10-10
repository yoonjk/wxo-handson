"""MCP Server — factorial tools (section-05/lab03)

Provides two tools via FastMCP:
  • factorial_value  – returns the exact integer value of n!
  • factorial_digits – returns only the number of decimal digits of n!
"""

import math

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("factorial-server")


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _compute_factorial(n: int) -> int:
    """Return n!  Raises ValueError for negative inputs."""
    if n < 0:
        raise ValueError(f"Input must be a non-negative integer, got {n}")
    return math.factorial(n)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def factorial_value(n: int) -> str:
    """음이 아닌 정수 n을 입력받아 n! (n factorial)의 정확한 값을 계산해 반환합니다.

    Args:
        n: 음이 아닌 정수 (non-negative integer).

    Returns:
        n!의 정확한 10진수(decimal) 값을 문자열(string)로 반환합니다.
    """
    result = _compute_factorial(n)
    return str(result)


@mcp.tool()
def factorial_digits(n: int) -> int:
    """n! (n factorial)의 10진수(decimal) 자릿수만 반환합니다.

    n!의 값이 너무 커서 전체 값을 표시하기 어려울 때 유용합니다.

    Args:
        n: 음이 아닌 정수 (non-negative integer).

    Returns:
        n!의 10진수(decimal) 자릿수(digit count)를 integer로 반환합니다.
    """
    result = _compute_factorial(n)
    return len(str(result))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
