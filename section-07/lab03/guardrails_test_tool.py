from ibm_watsonx_orchestrate.agent_builder.tools import tool


@tool
def guardrails_test_tool(text: str) -> str:
    """Return a safe marker and the character count for a guardrails test input."""
    return f"DEMO_TOOL_OK: {len(text)} characters received."
