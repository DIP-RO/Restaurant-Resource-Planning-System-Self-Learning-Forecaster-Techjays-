from __future__ import annotations

import csv
import math
from pathlib import Path


DEFAULT_RULES = {
    "server": {"covers_per_staff": 18, "minimum_staff": 1, "active_from": 10, "active_to": 23},
    "line_cook": {"covers_per_staff": 22, "minimum_staff": 1, "active_from": 10, "active_to": 23},
    "prep_cook": {"covers_per_staff": 45, "minimum_staff": 1, "active_from": 10, "active_to": 23},
    "host": {"covers_per_staff": 55, "minimum_staff": 1, "active_from": 10, "active_to": 23},
    "bartender": {"covers_per_staff": 35, "minimum_staff": 0, "active_from": 16, "active_to": 23},
    "dishwasher": {"covers_per_staff": 40, "minimum_staff": 1, "active_from": 10, "active_to": 23},
    "manager": {"covers_per_staff": 999, "minimum_staff": 1, "active_from": 10, "active_to": 23},
}


def load_staff_rules(path: str | Path | None) -> dict[str, dict[str, int]]:
    if path is None or not Path(path).exists():
        return DEFAULT_RULES
    rules: dict[str, dict[str, int]] = {}
    with Path(path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            rules[row["role"]] = {
                "covers_per_staff": int(row["covers_per_staff"]),
                "minimum_staff": int(row["minimum_staff"]),
                "active_from": int(row["active_from"]),
                "active_to": int(row["active_to"]),
            }
    return rules


def calculate_staffing(
    hourly_covers: dict[int, float],
    rules: dict[str, dict[str, int]],
) -> dict[int, dict[str, int]]:
    schedule: dict[int, dict[str, int]] = {}
    for hour, covers in hourly_covers.items():
        schedule[hour] = {}
        for role, rule in rules.items():
            if hour < rule["active_from"] or hour > rule["active_to"]:
                schedule[hour][role] = 0
                continue
            needed = math.ceil(covers / max(rule["covers_per_staff"], 1))
            schedule[hour][role] = max(rule["minimum_staff"], needed)
    return schedule
