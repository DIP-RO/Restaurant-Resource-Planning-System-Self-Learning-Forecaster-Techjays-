from __future__ import annotations

import argparse
import json
from pathlib import Path

from .forecaster import RestaurantForecaster


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def build_forecaster() -> RestaurantForecaster:
    return RestaurantForecaster(
        DATA / "sales_history.csv",
        DATA / "menu_recipes.csv",
        DATA / "ingredients.csv",
        ROOT / ".model_state.json",
        DATA / "staff_rules.csv",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaurant resource planning forecaster")
    subparsers = parser.add_subparsers(dest="command", required=True)

    forecast = subparsers.add_parser("forecast", help="Predict covers, staffing, and ingredient order")
    forecast.add_argument("--date", required=True)
    forecast.add_argument("--weather", default="clear")
    forecast.add_argument("--event", default="none")
    forecast.add_argument("--holiday", action="store_true")
    forecast.add_argument("--on-hand", default="{}", help='JSON map, e.g. \'{"chicken_kg": 4}\'')

    correction = subparsers.add_parser("correct", help="Apply manager feedback and update coefficients")
    correction.add_argument("--date", required=True)
    correction.add_argument("--weather", default="clear")
    correction.add_argument("--event", default="none")
    correction.add_argument("--holiday", action="store_true")
    correction.add_argument("--actual", required=True, help='JSON map of hour to covers, e.g. \'{"18": 32}\'')
    correction.add_argument("--reason", default="")

    args = parser.parse_args()
    forecaster = build_forecaster()
    try:
        if args.command == "forecast":
            result = forecaster.forecast(
                args.date,
                weather=args.weather,
                event=args.event,
                holiday=args.holiday,
                on_hand=json.loads(args.on_hand),
            )
        else:
            result = forecaster.apply_correction(
                args.date,
                actual_covers_by_hour=json.loads(args.actual),
                weather=args.weather,
                event=args.event,
                holiday=args.holiday,
                reason=args.reason,
            )
    except json.JSONDecodeError as exc:
        parser.error(f"invalid JSON input: {exc}")
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
