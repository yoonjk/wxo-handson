from mcp.server.fastmcp import FastMCP
import math

# MCP Server
mcp = FastMCP("math_toolkit")


@mcp.tool()
def square_root(x: float) -> float:
    """Calculate the square root of a number."""
    if x < 0:
        raise ValueError("x must be greater than or equal to 0")

    return math.sqrt(x)


@mcp.tool()
def power(base: float, exponent: float) -> float:
    """Calculate base raised to exponent."""
    return math.pow(base, exponent)


if __name__ == "__main__":
    mcp.run()