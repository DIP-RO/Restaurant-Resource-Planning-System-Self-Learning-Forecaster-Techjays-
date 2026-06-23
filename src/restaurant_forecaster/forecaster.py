from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from json import JSONDecodeError
from pathlib import Path
from statistics import mean
from typing import Any

from .feedback import apply_bounded_multiplier, clamp
from .inventory import plan_ingredient_orders
from .staffing import calculate_staffing, load_staff_rules


SERVICE_HOURS = list(range(10, 24))
REQUIRED_HISTORY_COLUMNS = {
    "date",
    "weekday",
    "hour",
    "weather",
    "event",
    "covers",
    "top_dish",
    "dish_orders",
}
REQUIRED_RECIPE_COLUMNS = {"dish", "ingredient"}
REQUIRED_INGREDIENT_COLUMNS = {
    "ingredient",
    "current_stock",
    "unit",
    "shelf_life_days",
    "supplier_lead_time_days",
    "min_order_qty",
}


@dataclass(frozen=True)
class DayContext:
    target_date: date
    weather: str = "clear"
    event: str = "none"
    holiday: bool = False

    @property
    def weekday(self) -> str:
        return self.target_date.strftime("%A").lower()


class RestaurantForecaster:
    """Self-learning forecaster for covers, staffing, and ingredient ordering."""

    def __init__(
        self,
        history_path: str | Path,
        recipes_path: str | Path,
        ingredients_path: str | Path,
        model_path: str | Path = ".model_state.json",
        staff_rules_path: str | Path | None = None,
    ) -> None:
        self.history_path = Path(history_path)
        self.recipes_path = Path(recipes_path)
        self.ingredients_path = Path(ingredients_path)
        self.model_path = Path(model_path)
        self.history = self._read_csv(self.history_path)
        self.recipes = self._load_recipes()
        self.ingredients = self._load_ingredients()
        self.staff_rules = load_staff_rules(staff_rules_path)
        self.state = self._load_or_train_state()
        self._validate_state(self.state)

    def forecast(
        self,
        target_date: str | date,
        weather: str = "clear",
        event: str = "none",
        holiday: bool = False,
        on_hand: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        context = DayContext(self._parse_date(target_date), weather, event, holiday)
        self._validate_context(context)
        clean_on_hand = self._validate_stock(on_hand or {})
        hourly_covers = self._forecast_covers(context)
        total_covers = sum(hourly_covers.values())
        staffing = calculate_staffing(hourly_covers, self.staff_rules)
        ingredients = self._forecast_ingredients(total_covers, context.target_date, clean_on_hand)
        return {
            "date": context.target_date.isoformat(),
            "context": {
                "weekday": context.weekday,
                "weather": weather,
                "event": event,
                "holiday": holiday,
            },
            "covers_by_hour": hourly_covers,
            "total_covers": round(total_covers, 1),
            "staffing_by_hour": staffing,
            "ingredient_order": ingredients,
        }

    def apply_correction(
        self,
        target_date: str | date,
        actual_covers_by_hour: dict[int | str, float],
        weather: str = "clear",
        event: str = "none",
        holiday: bool = False,
        reason: str = "",
    ) -> dict[str, Any]:
        """Update coefficients from manager feedback and persist the new model."""
        context = DayContext(self._parse_date(target_date), weather, event, holiday)
        self._validate_context(context)
        predicted = self._forecast_covers(context)
        actual = self._validate_actual_covers(actual_covers_by_hour)
        predicted_total = sum(predicted.values())
        actual_total = sum(actual.values())
        ratio = clamp(actual_total / max(predicted_total, 1.0), 0.45, 1.85)
        learning_rate = float(self.state["learning_rate"])
        multiplier_delta = 1 + ((ratio - 1) * learning_rate)

        self._nudge_factor("weather_factors", weather, multiplier_delta)
        self._nudge_factor("event_factors", event, multiplier_delta)
        self._nudge_factor("weekday_factors", context.weekday, multiplier_delta)
        if holiday:
            self._nudge_factor("event_factors", "holiday", multiplier_delta)

        shape = self.state["hourly_shape"]
        for hour in SERVICE_HOURS:
            predicted_share = predicted.get(hour, 0) / max(predicted_total, 1.0)
            actual_share = actual.get(hour, 0) / max(actual_total, 1.0)
            shape[str(hour)] = clamp(
                shape[str(hour)] + ((actual_share - predicted_share) * learning_rate),
                0.005,
                0.25,
            )
        self._normalize_hourly_shape()

        self.state["corrections"].append(
            {
                "date": context.target_date.isoformat(),
                "reason": reason,
                "weather": weather,
                "event": event,
                "holiday": holiday,
                "predicted_total": round(predicted_total, 2),
                "actual_total": round(actual_total, 2),
                "ratio": round(ratio, 4),
            }
        )
        self.save()
        return {
            "predicted_total": round(predicted_total, 1),
            "actual_total": round(actual_total, 1),
            "adjustment_ratio": round(ratio, 3),
            "updated_weather_factor": round(self.state["weather_factors"].get(weather, 1.0), 3),
            "updated_event_factor": round(self.state["event_factors"].get(event, 1.0), 3),
            "message": "Model coefficients updated from manager correction.",
        }

    def save(self) -> None:
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_path.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n")

    def _forecast_covers(self, context: DayContext) -> dict[int, float]:
        state = self.state
        base = float(state["base_daily_covers"])
        factor = (
            state["weekday_factors"].get(context.weekday, 1.0)
            * state["weather_factors"].get(context.weather, 1.0)
            * state["event_factors"].get(context.event, 1.0)
            * (state["event_factors"].get("holiday", 1.0) if context.holiday else 1.0)
        )
        total = max(5.0, base * factor)
        return {
            hour: round(total * float(state["hourly_shape"][str(hour)]), 1)
            for hour in SERVICE_HOURS
        }

    def _forecast_ingredients(
        self,
        total_covers: float,
        target_date: date,
        on_hand: dict[str, float],
    ) -> list[dict[str, Any]]:
        return plan_ingredient_orders(
            total_covers,
            target_date,
            self.state["menu_mix"],
            self.recipes,
            self.ingredients,
            on_hand,
        )

    def _load_or_train_state(self) -> dict[str, Any]:
        if self.model_path.exists():
            try:
                return json.loads(self.model_path.read_text())
            except JSONDecodeError as exc:
                raise ValueError(f"invalid model state JSON at {self.model_path}") from exc
        state = self._train_initial_state()
        self.state = state
        self.save()
        return state

    def _train_initial_state(self) -> dict[str, Any]:
        self._validate_rows("history", self.history, REQUIRED_HISTORY_COLUMNS)
        daily_totals: dict[str, float] = {}
        weekday_totals: dict[str, list[float]] = {}
        weather_totals: dict[str, list[float]] = {}
        event_totals: dict[str, list[float]] = {}
        hourly_totals = {hour: 0.0 for hour in SERVICE_HOURS}
        menu_totals: dict[str, float] = {}
        total_orders = 0.0

        for row in self.history:
            day = row["date"]
            hour = int(row["hour"])
            if hour not in SERVICE_HOURS:
                raise ValueError(f"history hour {hour} is outside service hours {SERVICE_HOURS[0]}-{SERVICE_HOURS[-1]}")
            covers = float(row["covers"])
            dish_orders = float(row["dish_orders"])
            if covers < 0 or dish_orders < 0:
                raise ValueError("history covers and dish_orders cannot be negative")
            daily_totals[day] = daily_totals.get(day, 0.0) + covers
            hourly_totals[hour] += covers
            menu_totals[row["top_dish"]] = menu_totals.get(row["top_dish"], 0.0) + dish_orders
            total_orders += dish_orders

        day_meta = {row["date"]: row for row in self.history}
        for day, covers in daily_totals.items():
            row = day_meta[day]
            weekday_totals.setdefault(row["weekday"], []).append(covers)
            weather_totals.setdefault(row["weather"], []).append(covers)
            event_totals.setdefault(row["event"], []).append(covers)

        base = mean(daily_totals.values())
        return {
            "base_daily_covers": round(base, 3),
            "learning_rate": 0.18,
            "weekday_factors": self._factors_from_totals(weekday_totals, base),
            "weather_factors": self._factors_from_totals(weather_totals, base),
            "event_factors": self._factors_from_totals(event_totals, base) | {"holiday": 1.18},
            "hourly_shape": {
                str(hour): round(hourly_totals[hour] / max(sum(hourly_totals.values()), 1.0), 5)
                for hour in SERVICE_HOURS
            },
            "menu_mix": {
                dish: round(count / max(total_orders, 1.0), 5)
                for dish, count in sorted(menu_totals.items())
            },
            "corrections": [],
        }

    def _load_recipes(self) -> dict[str, dict[str, float]]:
        rows = self._read_csv(self.recipes_path)
        self._validate_rows("recipes", rows, REQUIRED_RECIPE_COLUMNS)
        recipes: dict[str, dict[str, float]] = {}
        for row in rows:
            quantity = row.get("quantity_per_dish", row.get("quantity_per_cover", "0"))
            quantity_value = float(quantity)
            if quantity_value < 0:
                raise ValueError("recipe quantities cannot be negative")
            recipes.setdefault(row["dish"], {})[row["ingredient"]] = quantity_value
        return recipes

    def _load_ingredients(self) -> dict[str, dict[str, str]]:
        rows = self._read_csv(self.ingredients_path)
        self._validate_rows("ingredients", rows, REQUIRED_INGREDIENT_COLUMNS)
        ingredients = {row["ingredient"]: row for row in rows}
        for name, row in ingredients.items():
            if float(row["current_stock"]) < 0:
                raise ValueError(f"ingredient {name} has negative current_stock")
            if int(row["shelf_life_days"]) <= 0:
                raise ValueError(f"ingredient {name} must have positive shelf_life_days")
            if int(row["supplier_lead_time_days"]) < 0:
                raise ValueError(f"ingredient {name} cannot have negative supplier_lead_time_days")
            if float(row["min_order_qty"]) < 0:
                raise ValueError(f"ingredient {name} cannot have negative min_order_qty")
        return ingredients

    @staticmethod
    def _validate_rows(name: str, rows: list[dict[str, str]], required_columns: set[str]) -> None:
        if not rows:
            raise ValueError(f"{name} data is empty")
        missing = required_columns - set(rows[0])
        if missing:
            raise ValueError(f"{name} data is missing required columns: {', '.join(sorted(missing))}")

    @staticmethod
    def _validate_state(state: dict[str, Any]) -> None:
        required_keys = {
            "base_daily_covers",
            "learning_rate",
            "weekday_factors",
            "weather_factors",
            "event_factors",
            "hourly_shape",
            "menu_mix",
            "corrections",
        }
        missing = required_keys - set(state)
        if missing:
            raise ValueError(f"model state is missing required keys: {', '.join(sorted(missing))}")
        missing_hours = {str(hour) for hour in SERVICE_HOURS} - set(state["hourly_shape"])
        if missing_hours:
            raise ValueError(f"model state hourly_shape is missing hours: {', '.join(sorted(missing_hours))}")

    def _validate_context(self, context: DayContext) -> None:
        self._validate_factor("weather", context.weather, self.state["weather_factors"])
        self._validate_factor("event", context.event, self.state["event_factors"])

    @staticmethod
    def _validate_factor(name: str, value: str, factors: dict[str, float]) -> None:
        if value not in factors:
            allowed = ", ".join(sorted(factors))
            raise ValueError(f"unknown {name} '{value}'. Allowed values: {allowed}")

    @staticmethod
    def _validate_actual_covers(actual_covers_by_hour: dict[int | str, float]) -> dict[int, float]:
        if not actual_covers_by_hour:
            raise ValueError("actual_covers_by_hour must include at least one service hour")

        actual: dict[int, float] = {}
        for hour, value in actual_covers_by_hour.items():
            try:
                parsed_hour = int(hour)
                covers = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("correction hours and covers must be numeric") from exc

            if parsed_hour not in SERVICE_HOURS:
                raise ValueError(f"hour {parsed_hour} is outside service hours {SERVICE_HOURS[0]}-{SERVICE_HOURS[-1]}")
            if covers < 0:
                raise ValueError("actual covers cannot be negative")
            actual[parsed_hour] = covers
        return actual

    def _validate_stock(self, on_hand: dict[str, float]) -> dict[str, float]:
        clean_stock: dict[str, float] = {}
        for ingredient, value in on_hand.items():
            if ingredient not in self.ingredients:
                raise ValueError(f"unknown ingredient '{ingredient}' in on-hand stock")
            try:
                stock = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("on-hand stock values must be numeric") from exc
            if stock < 0:
                raise ValueError("on-hand stock cannot be negative")
            clean_stock[ingredient] = stock
        return clean_stock

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open(newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _parse_date(value: str | date) -> date:
        if isinstance(value, date):
            return value
        return datetime.strptime(value, "%Y-%m-%d").date()

    @staticmethod
    def _factors_from_totals(groups: dict[str, list[float]], base: float) -> dict[str, float]:
        return {
            key: round(clamp(mean(values) / max(base, 1.0), 0.55, 1.65), 4)
            for key, values in sorted(groups.items())
        }

    def _nudge_factor(self, group: str, key: str, multiplier_delta: float) -> None:
        factors = self.state[group]
        factors[key] = apply_bounded_multiplier(float(factors.get(key, 1.0)), multiplier_delta)

    def _normalize_hourly_shape(self) -> None:
        shape = self.state["hourly_shape"]
        total = sum(float(value) for value in shape.values())
        for hour in SERVICE_HOURS:
            shape[str(hour)] = round(float(shape[str(hour)]) / total, 5)
