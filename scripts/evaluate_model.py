from __future__ import annotations

import csv
import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = ROOT / "src"

import sys

sys.path.insert(0, str(SRC))

from restaurant_forecaster import RestaurantForecaster


def load_daily_actuals(path: Path) -> dict[str, dict[str, object]]:
    daily: dict[str, dict[str, object]] = {}
    hourly: dict[str, dict[int, float]] = defaultdict(dict)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            day = row["date"]
            hourly[day][int(row["hour"])] = float(row["covers"])
            daily[day] = {
                "weather": row["weather"],
                "event": row["event"],
                "holiday": row["holiday"] == "true",
            }

    for day, covers_by_hour in hourly.items():
        daily[day]["covers_by_hour"] = covers_by_hour
        daily[day]["total_covers"] = sum(covers_by_hour.values())
    return daily


def evaluate() -> dict[str, float]:
    # Use an isolated model state so evaluation never mutates the runtime model.
    with tempfile.TemporaryDirectory() as tmp_dir:
        forecaster = RestaurantForecaster(
            DATA / "sales_history.csv",
            DATA / "menu_recipes.csv",
            DATA / "ingredients.csv",
            Path(tmp_dir) / "eval_model_state.json",
            DATA / "staff_rules.csv",
        )
        actuals = load_daily_actuals(DATA / "sales_history.csv")

        absolute_errors = []
        squared_errors = []
        percentage_errors = []
        for day, actual in actuals.items():
            prediction = forecaster.forecast(
                day,
                weather=str(actual["weather"]),
                event=str(actual["event"]),
                holiday=bool(actual["holiday"]),
            )
            predicted_total = float(prediction["total_covers"])
            actual_total = float(actual["total_covers"])
            error = predicted_total - actual_total
            absolute_errors.append(abs(error))
            squared_errors.append(error * error)
            if actual_total > 0:
                percentage_errors.append(abs(error) / actual_total)

    return {
        "days_evaluated": float(len(actuals)),
        "mae": round(sum(absolute_errors) / len(absolute_errors), 3),
        "rmse": round(math.sqrt(sum(squared_errors) / len(squared_errors)), 3),
        "mape_percent": round((sum(percentage_errors) / len(percentage_errors)) * 100, 3),
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
