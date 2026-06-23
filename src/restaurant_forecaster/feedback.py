from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def apply_bounded_multiplier(value: float, multiplier: float) -> float:
    return round(clamp(value * multiplier, 0.45, 1.9), 5)
