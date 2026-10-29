"""
test_lab02.py — unit tests for Python Tool and Python Toolkit

@tool 데코레이터 적용 후 반환값은 ToolResponse 객체이므로
str(result.content) 또는 result.content 로 검증합니다.

pytest section-05/lab02/test_lab02.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unit_convert import unit_convert
from math_toolkit.tools import square_root, power


def val(result) -> str:
    """ToolResponse 또는 str 모두 처리."""
    return str(result.content) if hasattr(result, "content") else str(result)


# ─── unit_convert (Python Tool) ────────────────────────────────────────────

class TestUnitConvert:

    def test_km_to_mile(self):
        assert "62.1371" in val(unit_convert(100, "km", "mile"))

    def test_mile_to_km(self):
        assert "1.6093" in val(unit_convert(1, "mile", "km"))

    def test_kg_to_lb(self):
        assert "2.2046" in val(unit_convert(1, "kg", "lb"))

    def test_lb_to_kg(self):
        assert "0.4536" in val(unit_convert(1, "lb", "kg"))

    def test_celsius_to_fahrenheit(self):
        assert "32.0" in val(unit_convert(0, "c", "f"))

    def test_fahrenheit_to_celsius(self):
        assert "0.0" in val(unit_convert(32, "f", "c"))

    def test_boiling_point(self):
        assert "212.0" in val(unit_convert(100, "c", "f"))

    def test_same_unit(self):
        assert "50" in val(unit_convert(50, "km", "km"))

    def test_case_insensitive(self):
        assert "0.6214" in val(unit_convert(1, "KM", "MILE"))

    def test_unsupported_conversion(self):
        with pytest.raises(Exception):
            unit_convert(1, "km", "kg")

    def test_whitespace_in_unit(self):
        assert "0.6214" in val(unit_convert(1, " km ", " mile "))

    def test_zero_value(self):
        assert "0" in val(unit_convert(0, "km", "mile"))

    def test_negative_value_distance(self):
        assert "-6.2137" in val(unit_convert(-10, "km", "mile"))


# ─── square_root (Python Toolkit) ──────────────────────────────────────────

class TestSquareRoot:

    def test_perfect_square(self):
        assert "12.0" in val(square_root(144))

    def test_irrational(self):
        assert "1.414214" in val(square_root(2))

    def test_zero(self):
        assert "0.0" in val(square_root(0))

    def test_one(self):
        assert "1.0" in val(square_root(1))

    def test_fractional(self):
        assert "0.5" in val(square_root(0.25))

    def test_negative_raises(self):
        with pytest.raises(Exception):
            square_root(-1)

    def test_large_number(self):
        assert "1000.0" in val(square_root(1_000_000))


# ─── power (Python Toolkit) ────────────────────────────────────────────────

class TestPower:

    def test_integer_exponent(self):
        assert "1024.0" in val(power(2, 10))

    def test_zero_exponent(self):
        assert "1.0" in val(power(99, 0))

    def test_one_exponent(self):
        assert "5.0" in val(power(5, 1))

    def test_negative_exponent(self):
        assert "0.5" in val(power(2, -1))

    def test_fractional_exponent(self):
        assert "3.0" in val(power(9, 0.5))

    def test_zero_base(self):
        assert "0.0" in val(power(0, 5))

    def test_one_base(self):
        assert "1.0" in val(power(1, 1000))

    def test_large_power(self):
        assert "4294967296.0" in val(power(2, 32))

    def test_negative_base_integer_exp(self):
        assert "-8.0" in val(power(-2, 3))
