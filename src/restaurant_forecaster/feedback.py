from __future__ import annotations


def update_factor(old_value: float, actual: float, predicted: float, learning_rate: float) -> float:
    if predicted <= 0:
        return old_value
    actual_ratio = clamp(actual / predicted, 0.45, 1.85)
    new_value = old_value + (learning_rate * (actual_ratio - old_value))
    return round(clamp(new_value, 0.45, 1.9), 5)


def update_multiplier(old_value: float, actual: float, predicted: float, learning_rate: float) -> float:
    if predicted <= 0:
        return old_value
    ratio = clamp(actual / predicted, 0.45, 1.85)
    multiplier_delta = 1 + ((ratio - 1) * learning_rate)
    return round(clamp(old_value * multiplier_delta, 0.45, 1.9), 5)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
