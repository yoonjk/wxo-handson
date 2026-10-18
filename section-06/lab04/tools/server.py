"""
STDIO MCP Server — SQL Query Tool
Langflow REST API를 통해 MySQL 데이터베이스를 자연어로 조회합니다.

환경변수 (WXO key_value connection에서 주입):
  LANGFLOW_API_KEY  : Langflow 서버 API Key
"""

import os
import requests
from fastmcp import FastMCP

LANGFLOW_BASE_URL = "http://nexweb.ddnsgeek.com:3465"
FLOW_ID = "bfea7883-0b47-4aa4-99db-4357dbeb07cb"

mcp = FastMCP("sqlflow-mcp")


@mcp.tool()
def query_database(question: str) -> str:
    """Query the MySQL database using natural language and return results.

    Converts a natural language question into a SQL query, executes it
    against the connected MySQL demo database, and returns results in
    human-readable Korean format.

    Args:
        question: A natural language question about the database data.

    Returns:
        The query results as a human-readable string.
    """
    api_key = os.environ.get("LANGFLOW_API_KEY", "")

    url = f"{LANGFLOW_BASE_URL}/api/v1/run/{FLOW_ID}"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "input_value": question,
        "output_type": "chat",
        "input_type": "chat",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        for output_group in data.get("outputs", []):
            for output in output_group.get("outputs", []):
                msg = output.get("results", {}).get("message", {})
                text = msg.get("text") or msg.get("data", {}).get("text")
                if text:
                    return text

        return "No response received from the database query."

    except requests.exceptions.Timeout:
        return "Error: The database query timed out. Please try a simpler question."
    except requests.exceptions.RequestException as e:
        return f"Error: Failed to connect to the query service. {e}"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
