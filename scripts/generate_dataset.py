from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RANDOM = random.Random(42)

WEATHER_FACTORS = {"clear": 1.0, "rain": 0.72, "storm": 0.54, "hot": 0.9, "cold": 0.88}
EVENT_FACTORS = {"none": 1.0, "concert": 1.35, "sports": 1.25, "festival": 1.5}
WEEKDAY_FACTORS = {
    "monday": 0.72,
    "tuesday": 0.78,
    "wednesday": 0.85,
    "thursday": 0.96,
    "friday": 1.25,
    "saturday": 1.42,
    "sunday": 1.05,
}
HOURLY_SHAPE = {
    10: 0.025,
    11: 0.045,
    12: 0.105,
    13: 0.1,
    14: 0.06,
    15: 0.035,
    16: 0.04,
    17: 0.075,
    18: 0.125,
    19: 0.15,
    20: 0.125,
    21: 0.075,
    22: 0.03,
    23: 0.01,
}
MENU_MIX = {
    "roast_chicken": 0.26,
    "beef_burger": 0.22,
    "veggie_pasta": 0.2,
    "salmon_bowl": 0.17,
    "caesar_salad": 0.15,
}


def weighted_choice(options: dict[str, float]) -> str:
    marker = RANDOM.random()
    running = 0.0
    for key, weight in options.items():
        running += weight
        if marker <= running:
            return key
    return next(reversed(options))


def generate_history() -> None:
    start = date(2025, 1, 1)
    rows = []
    for offset in range(210):
        day = start + timedelta(days=offset)
        weekday = day.strftime("%A").lower()
        weather = weighted_choice({"clear": 0.48, "rain": 0.24, "storm": 0.08, "hot": 0.12, "cold": 0.08})
        event = weighted_choice({"none": 0.72, "concert": 0.1, "sports": 0.12, "festival": 0.06})
        holiday = day.month == 1 and day.day == 1
        daily = 110 * WEEKDAY_FACTORS[weekday] * WEATHER_FACTORS[weather] * EVENT_FACTORS[event]
        if holiday:
            daily *= 1.18
        daily *= 1 + (0.08 * math.sin(offset / 9)) + RANDOM.uniform(-0.08, 0.08)

        for hour, share in HOURLY_SHAPE.items():
            covers = max(0, round(daily * share * RANDOM.uniform(0.86, 1.14)))
            top_dish = weighted_choice(MENU_MIX)
            total_sales = covers * RANDOM.randint(38, 58)
            rows.append(
                {
                    "date": day.isoformat(),
                    "weekday": weekday,
                    "hour": hour,
                    "weather": weather,
                    "is_weekend": str(weekday in {"friday", "saturday", "sunday"}).lower(),
                    "event": event,
                    "has_event": str(event != "none").lower(),
                    "holiday": str(holiday).lower(),
                    "covers": covers,
                    "total_sales": total_sales,
                    "top_dish": top_dish,
                    "dish_orders": max(1, round(covers * MENU_MIX[top_dish] * RANDOM.uniform(0.8, 1.2))),
                }
            )
    write_csv(DATA / "sales_history.csv", rows)


def generate_static_tables() -> None:
    ingredients = [
        ("chicken_kg", 5, "kg", 3, 2, 2),
        ("beef_kg", 4, "kg", 4, 3, 2),
        ("salmon_kg", 3, "kg", 2, 2, 1),
        ("pasta_kg", 8, "kg", 30, 5, 2),
        ("rice_kg", 10, "kg", 20, 4, 5),
        ("lettuce_heads", 10, "heads", 4, 1, 4),
        ("tomato_kg", 5, "kg", 5, 1, 2),
        ("potato_kg", 12, "kg", 14, 3, 5),
        ("bun_each", 40, "each", 5, 2, 24),
        ("parmesan_kg", 2, "kg", 21, 4, 1),
        ("cream_l", 4, "liter", 7, 2, 2),
    ]
    write_csv(
        DATA / "ingredients.csv",
        [
            {
                "ingredient": name,
                "current_stock": current_stock,
                "unit": unit,
                "shelf_life_days": shelf_life,
                "supplier_lead_time_days": lead_time,
                "min_order_qty": min_order_qty,
            }
            for name, current_stock, unit, shelf_life, lead_time, min_order_qty in ingredients
        ],
    )

    staff_rules = [
        ("server", 18, 1, 10, 23),
        ("line_cook", 22, 1, 10, 23),
        ("prep_cook", 45, 1, 10, 23),
        ("host", 55, 1, 10, 23),
        ("bartender", 35, 0, 16, 23),
        ("dishwasher", 40, 1, 10, 23),
        ("manager", 999, 1, 10, 23),
    ]
    write_csv(
        DATA / "staff_rules.csv",
        [
            {
                "role": role,
                "covers_per_staff": covers_per_staff,
                "minimum_staff": minimum_staff,
                "active_from": active_from,
                "active_to": active_to,
            }
            for role, covers_per_staff, minimum_staff, active_from, active_to in staff_rules
        ],
    )

    corrections = [
        ("2025-07-10", 120, 85, "rain"),
        ("2025-07-11", 90, 130, "local_event"),
        ("2025-07-12", 160, 145, "storm"),
    ]
    write_csv(
        DATA / "manager_corrections.csv",
        [
            {
                "date": day,
                "predicted_covers": predicted,
                "actual_covers": actual,
                "reason": reason,
            }
            for day, predicted, actual, reason in corrections
        ],
    )

    recipe_rows = [
        ("roast_chicken", "chicken_kg", 0.22),
        ("roast_chicken", "potato_kg", 0.18),
        ("roast_chicken", "tomato_kg", 0.04),
        ("beef_burger", "beef_kg", 0.18),
        ("beef_burger", "bun_each", 1.0),
        ("beef_burger", "lettuce_heads", 0.05),
        ("beef_burger", "tomato_kg", 0.05),
        ("veggie_pasta", "pasta_kg", 0.16),
        ("veggie_pasta", "cream_l", 0.08),
        ("veggie_pasta", "parmesan_kg", 0.025),
        ("salmon_bowl", "salmon_kg", 0.19),
        ("salmon_bowl", "rice_kg", 0.14),
        ("salmon_bowl", "lettuce_heads", 0.04),
        ("caesar_salad", "lettuce_heads", 0.12),
        ("caesar_salad", "chicken_kg", 0.08),
        ("caesar_salad", "parmesan_kg", 0.02),
    ]
    ingredient_units = {
        "chicken_kg": "kg",
        "beef_kg": "kg",
        "salmon_kg": "kg",
        "pasta_kg": "kg",
        "rice_kg": "kg",
        "lettuce_heads": "heads",
        "tomato_kg": "kg",
        "potato_kg": "kg",
        "bun_each": "each",
        "parmesan_kg": "kg",
        "cream_l": "liter",
    }
    write_csv(
        DATA / "menu_recipes.csv",
        [
            {
                "dish": dish,
                "ingredient": ingredient,
                "quantity_per_dish": quantity,
                "unit": ingredient_units[ingredient],
            }
            for dish, ingredient, quantity in recipe_rows
        ],
    )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    DATA.mkdir(exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    generate_static_tables()
    generate_history()
