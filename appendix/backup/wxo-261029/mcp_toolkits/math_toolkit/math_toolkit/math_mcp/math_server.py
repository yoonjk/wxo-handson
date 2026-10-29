import math
import asyncio
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

app = Server("Math Toolkit MCP Server")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="square_root",
            description="Compute the square root of a non-negative number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "value": {"type": "number", "description": "A non-negative real number."}
                },
                "required": ["value"],
            },
        ),
        types.Tool(
            name="power",
            description="Raise a base number to the given exponent. Supports fractional and negative exponents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "base":     {"type": "number", "description": "The base number."},
                    "exponent": {"type": "number", "description": "The exponent."},
                },
                "required": ["base", "exponent"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "square_root":
        value = float(arguments["value"])
        if value < 0:
            raise ValueError(f"Cannot compute square root of a negative number: {value}")
        result = math.sqrt(value)
        return [types.TextContent(type="text", text=f"√{value} = {round(result, 6)}")]
    elif name == "power":
        base = float(arguments["base"])
        exponent = float(arguments["exponent"])
        result = math.pow(base, exponent)
        return [types.TextContent(type="text", text=f"{base}^{exponent} = {round(result, 6)}")]
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
