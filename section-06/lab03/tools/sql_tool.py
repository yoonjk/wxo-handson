from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
from ibm_watsonx_orchestrate.run import connections

APP_ID = "langflow_sqlflow"

FLOW_ID = "bfea7883-0b47-4aa4-99db-4357dbeb07cb"
LANGFLOW_BASE_URL = "http://nexweb.ddnsgeek.com:3465"


@tool(
    permission=ToolPermission.READ_ONLY,
    expected_credentials=[
        ExpectedCredentials(app_id=APP_ID, type=ConnectionType.API_KEY_AUTH)
    ],
)
def query_database(question: str) -> str:
    """Query the MySQL database using natural language and return the results.

    Converts the user's natural language question into a SQL query,
    executes it against the connected MySQL database, and returns
    the results in a human-readable format.

    Args:
        question (str): A natural language question about the database data.
    Returns:
        str: The query results formatted as a readable response in natural language.
    """
    import requests

    creds = connections.api_key_auth(APP_ID)
    api_key = creds.api_key

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
                results = output.get("results", {})
                msg = results.get("message", {})
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
