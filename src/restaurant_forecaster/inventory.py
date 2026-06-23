from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def plan_ingredient_orders(
    total_covers: float,
    target_date: date,
    menu_mix: dict[str, float],
    recipes: dict[str, dict[str, float]],
    ingredients: dict[str, dict[str, str]],
    on_hand: dict[str, float],
) -> list[dict[str, Any]]:
    demand: dict[str, float] = {name: 0.0 for name in ingredients}
    for dish, expected_share in menu_mix.items():
        dish_count = total_covers * expected_share
        for ingredient, quantity in recipes.get(dish, {}).items():
            demand[ingredient] = demand.get(ingredient, 0.0) + (dish_count * quantity)

    orders = []
    for ingredient, required in demand.items():
        meta = ingredients[ingredient]
        current_stock = float(on_hand.get(ingredient, meta.get("current_stock", 0) or 0))
        shelf_life = int(meta["shelf_life_days"])
        lead_time = int(meta.get("supplier_lead_time_days", meta.get("lead_time_days", 0)))
        min_order_qty = float(meta.get("min_order_qty", 0) or 0)
        safety_buffer = 1 + min(shelf_life * 0.015, 0.12)
        order_quantity = max(0.0, (required * safety_buffer) - current_stock)
        if order_quantity <= 0.05:
            continue
        order_quantity = max(order_quantity, min_order_qty)
        order_by = target_date - timedelta(days=lead_time)
        orders.append(
            {
                "ingredient": ingredient,
                "required_quantity": round(required, 2),
                "current_stock": round(current_stock, 2),
                "order_quantity": round(order_quantity, 2),
                "unit": meta["unit"],
                "order_by": order_by.isoformat(),
                "supplier_lead_time_days": lead_time,
                "shelf_life_days": shelf_life,
            }
        )
    return sorted(orders, key=lambda row: (row["order_by"], row["ingredient"]))
