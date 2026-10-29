"""
unit_convert.py — Python Tool (single function)

watsonx Orchestrate에 --kind python 으로 등록되는 단일 함수 Tool.
호출할 때마다 subprocess가 새로 생성되는 stateless 방식.

지원 변환:
  km   → mile  / mile  → km
  kg   → lb    / lb    → kg
  c    → f     / f     → c
"""

from ibm_watsonx_orchestrate.agent_builder.tools import tool


@tool
def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    """Convert a numeric value between common units.

    Supported conversions:
      - Distance : km ↔ mile
      - Weight   : kg ↔ lb
      - Temperature: c ↔ f

    Args:
        value: The numeric value to convert.
        from_unit: Source unit. One of: km, mile, kg, lb, c, f
        to_unit:   Target unit. One of: km, mile, kg, lb, c, f

    Returns:
        A human-readable string with the converted value and unit.
    """
    from_unit = from_unit.strip().lower()
    to_unit = to_unit.strip().lower()

    CONVERSIONS: dict = {
        ("km", "mile"): 0.621371,
        ("mile", "km"): 1.60934,
        ("kg", "lb"): 2.20462,
        ("lb", "kg"): 0.453592,
    }

    pair = (from_unit, to_unit)

    if pair in CONVERSIONS:
        result = value * CONVERSIONS[pair]
        return f"{value} {from_unit} = {round(result, 4)} {to_unit}"

    if pair == ("c", "f"):
        result = value * 9 / 5 + 32
        return f"{value} °C = {round(result, 4)} °F"
    if pair == ("f", "c"):
        result = (value - 32) * 5 / 9
        return f"{value} °F = {round(result, 4)} °C"

    if from_unit == to_unit:
        return f"{value} {from_unit} = {value} {to_unit}"

    supported = "km↔mile, kg↔lb, c↔f"
    raise ValueError(
        f"Unsupported conversion: '{from_unit}' → '{to_unit}'. "
        f"Supported: {supported}"
    )
