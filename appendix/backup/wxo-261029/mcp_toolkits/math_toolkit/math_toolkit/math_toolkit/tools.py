"""
math_toolkit/tools.py — Python Toolkit (multiple functions)

watsonx Orchestrate에 orchestrate toolkits add --kind python 으로 등록.
--package-root 로 디렉토리 전체를 업로드하고 --tier 로 전용 자원 할당.
프로세스가 상주(warm)하므로 반복 호출 시 cold start 비용 없음.
"""

import math
from ibm_watsonx_orchestrate.agent_builder.tools import tool


@tool
def square_root(value: float) -> str:
    """Compute the square root of a non-negative number.

    Args:
        value: A non-negative real number.

    Returns:
        A string showing the input and its square root, rounded to 6 decimal places.
    """
    if value < 0:
        raise ValueError(f"Cannot compute square root of a negative number: {value}")
    result = math.sqrt(value)
    return f"√{value} = {round(result, 6)}"


@tool
def power(base: float, exponent: float) -> str:
    """Raise a base number to the given exponent.

    Supports fractional and negative exponents.

    Args:
        base:     The base number.
        exponent: The exponent (supports fractional and negative values).

    Returns:
        A string showing base^exponent and its result, rounded to 6 decimal places.
    """
    result = math.pow(base, exponent)
    return f"{base}^{exponent} = {round(result, 6)}"
