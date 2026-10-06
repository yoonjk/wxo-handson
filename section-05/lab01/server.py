import math
from fastmcp import FastMCP

mcp = FastMCP(
    name="Factorial MCP Server",
    description="Provides tools to compute factorial values and digit counts.",
)


def _compute_factorial(n: int) -> int:
    """Shared helper: compute n! for a non-negative integer n."""
    if n < 0:
        raise ValueError(f"n must be a non-negative integer, got {n}")
    return math.factorial(n)


@mcp.tool()
def factorial_value(n: int) -> str:
    """Return the exact value of n! (n factorial).

    Args:
        n: A non-negative integer.

    Returns:
        The exact decimal value of n! as a string.
    """
    result = _compute_factorial(n)
    return str(result)


@mcp.tool()
def factorial_digits(n: int) -> int:
    """Return the number of decimal digits in n! (n factorial).

    Useful when n! is too large to display in full.

    Args:
        n: A non-negative integer.

    Returns:
        The number of decimal digits in n!.
    """
    result = _compute_factorial(n)
    return len(str(result))


if __name__ == "__main__":
    mcp.run()
