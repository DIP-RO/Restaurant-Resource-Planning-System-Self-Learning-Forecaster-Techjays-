from pathlib import Path

import json
import pytest

from restaurant_forecaster import RestaurantForecaster


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def build_forecaster(tmp_path):
    return RestaurantForecaster(
        DATA / "sales_history.csv",
        DATA / "menu_recipes.csv",
        DATA / "ingredients.csv",
        tmp_path / "model_state.json",
        DATA / "staff_rules.csv",
    )


def test_forecast_includes_covers_staffing_and_ingredients(tmp_path):
    forecaster = build_forecaster(tmp_path)
    result = forecaster.forecast(
        "2025-08-01",
        weather="clear",
        event="concert",
        on_hand={"chicken_kg": 3, "bun_each": 10},
    )

    assert result["total_covers"] > 0
    assert set(result["covers_by_hour"]) == set(range(10, 24))
    assert result["staffing_by_hour"][19]["server"] >= 1
    assert result["staffing_by_hour"][19]["manager"] == 1
    assert result["ingredient_order"]
    assert all("order_by" in row for row in result["ingredient_order"])
    assert all("order_quantity" in row for row in result["ingredient_order"])


def test_correction_updates_future_weather_factor(tmp_path):
    forecaster = build_forecaster(tmp_path)
    before = forecaster.state["weather_factors"]["rain"]
    actual = {
        10: 1,
        11: 2,
        12: 7,
        13: 6,
        14: 4,
        15: 2,
        16: 3,
        17: 5,
        18: 8,
        19: 9,
        20: 7,
        21: 5,
        22: 2,
        23: 1,
    }

    correction = forecaster.apply_correction(
        "2025-08-02",
        actual,
        weather="rain",
        event="none",
        reason="Unexpected downpour",
    )

    assert correction["actual_total"] < correction["predicted_total"]
    assert forecaster.state["weather_factors"]["rain"] < before
    assert forecaster.model_path.exists()


def test_weather_and_event_context_change_cover_forecast(tmp_path):
    forecaster = build_forecaster(tmp_path)

    clear_none = forecaster.forecast("2025-08-01", weather="clear", event="none")
    storm_none = forecaster.forecast("2025-08-01", weather="storm", event="none")
    clear_concert = forecaster.forecast("2025-08-01", weather="clear", event="concert")

    assert clear_none["total_covers"] > storm_none["total_covers"]
    assert clear_concert["total_covers"] > clear_none["total_covers"]


def test_high_on_hand_stock_can_eliminate_ingredient_orders(tmp_path):
    forecaster = build_forecaster(tmp_path)
    result = forecaster.forecast(
        "2025-08-01",
        weather="clear",
        event="none",
        on_hand={
            "chicken_kg": 999,
            "beef_kg": 999,
            "salmon_kg": 999,
            "pasta_kg": 999,
            "rice_kg": 999,
            "lettuce_heads": 999,
            "tomato_kg": 999,
            "potato_kg": 999,
            "bun_each": 999,
            "parmesan_kg": 999,
            "cream_l": 999,
        },
    )

    assert result["ingredient_order"] == []


def test_correction_persists_and_reloads_model_state(tmp_path):
    model_path = tmp_path / "model_state.json"
    forecaster = RestaurantForecaster(
        DATA / "sales_history.csv",
        DATA / "menu_recipes.csv",
        DATA / "ingredients.csv",
        model_path,
        DATA / "staff_rules.csv",
    )
    before = forecaster.state["weather_factors"]["rain"]
    forecaster.apply_correction(
        "2025-08-02",
        {hour: 1 for hour in range(10, 24)},
        weather="rain",
        event="none",
        reason="rain",
    )

    reloaded = RestaurantForecaster(
        DATA / "sales_history.csv",
        DATA / "menu_recipes.csv",
        DATA / "ingredients.csv",
        model_path,
        DATA / "staff_rules.csv",
    )

    assert reloaded.state["weather_factors"]["rain"] == forecaster.state["weather_factors"]["rain"]
    assert reloaded.state["weather_factors"]["rain"] < before
    assert len(reloaded.state["corrections"]) == 1


def test_invalid_correction_hour_is_rejected(tmp_path):
    forecaster = build_forecaster(tmp_path)

    with pytest.raises(ValueError, match="outside service hours"):
        forecaster.apply_correction("2025-08-02", {9: 10}, weather="clear")


def test_negative_actual_covers_are_rejected(tmp_path):
    forecaster = build_forecaster(tmp_path)

    with pytest.raises(ValueError, match="cannot be negative"):
        forecaster.apply_correction("2025-08-02", {10: -1}, weather="clear")


def test_negative_on_hand_stock_is_rejected(tmp_path):
    forecaster = build_forecaster(tmp_path)

    with pytest.raises(ValueError, match="stock cannot be negative"):
        forecaster.forecast("2025-08-02", on_hand={"chicken_kg": -3})


def test_weather_alias_is_normalized(tmp_path):
    forecaster = build_forecaster(tmp_path)
    rainy = forecaster.forecast("2025-08-02", weather="rainy")
    rain = forecaster.forecast("2025-08-02", weather="rain")

    assert rainy["context"]["normalized_weather"] == "rain"
    assert rainy["total_covers"] == rain["total_covers"]


def test_unseen_event_forecasts_with_learned_fallback_and_warning(tmp_path):
    forecaster = build_forecaster(tmp_path)
    baseline = forecaster.forecast("2025-08-02", event="none")
    parade = forecaster.forecast("2025-08-02", event="parade")
    fallback = forecaster.state["fallback_factors"]["event"]

    assert parade["context"]["normalized_event"] == "parade"
    assert parade["warnings"] == [f"unseen event 'parade' used learned fallback factor {fallback:.3f}"]
    assert parade["total_covers"] > 0
    assert parade["total_covers"] != baseline["total_covers"]


def test_unseen_event_correction_creates_learned_factor(tmp_path):
    forecaster = build_forecaster(tmp_path)
    assert "parade" not in forecaster.state["event_factors"]
    fallback = forecaster.state["fallback_factors"]["event"]

    correction = forecaster.apply_correction("2025-08-02", {hour: 20 for hour in range(10, 24)}, event="parade")

    assert "parade" in forecaster.state["event_factors"]
    assert correction["warnings"] == [f"unseen event 'parade' initialized with learned fallback factor {fallback:.3f}"]
    assert forecaster.state["event_factors"]["parade"] != fallback


def test_unknown_on_hand_ingredient_is_rejected(tmp_path):
    forecaster = build_forecaster(tmp_path)

    with pytest.raises(ValueError, match="unknown ingredient"):
        forecaster.forecast("2025-08-02", on_hand={"chikcen_kg": 3})


def test_empty_history_data_is_rejected(tmp_path):
    history = tmp_path / "empty_history.csv"
    history.write_text("date,weekday,hour,weather,event,covers,top_dish,dish_orders\n")

    with pytest.raises(ValueError, match="history data is empty"):
        RestaurantForecaster(
            history,
            DATA / "menu_recipes.csv",
            DATA / "ingredients.csv",
            tmp_path / "model_state.json",
            DATA / "staff_rules.csv",
        )


def test_history_missing_required_columns_is_rejected(tmp_path):
    history = tmp_path / "bad_history.csv"
    history.write_text("date,hour,covers\n2025-01-01,10,5\n")

    with pytest.raises(ValueError, match="missing required columns"):
        RestaurantForecaster(
            history,
            DATA / "menu_recipes.csv",
            DATA / "ingredients.csv",
            tmp_path / "model_state.json",
            DATA / "staff_rules.csv",
        )


def test_corrupted_model_state_is_rejected(tmp_path):
    model_path = tmp_path / "model_state.json"
    model_path.write_text("{not valid json")

    with pytest.raises(ValueError, match="invalid model state JSON"):
        RestaurantForecaster(
            DATA / "sales_history.csv",
            DATA / "menu_recipes.csv",
            DATA / "ingredients.csv",
            model_path,
            DATA / "staff_rules.csv",
        )


def test_incomplete_model_state_is_rejected(tmp_path):
    model_path = tmp_path / "model_state.json"
    model_path.write_text(json.dumps({"base_daily_covers": 100}))

    with pytest.raises(ValueError, match="model state is missing required keys"):
        RestaurantForecaster(
            DATA / "sales_history.csv",
            DATA / "menu_recipes.csv",
            DATA / "ingredients.csv",
            model_path,
            DATA / "staff_rules.csv",
        )


def test_extreme_corrections_keep_coefficients_and_hourly_shape_bounded(tmp_path):
    forecaster = build_forecaster(tmp_path)

    forecaster.apply_correction(
        "2025-08-02",
        {hour: 0 for hour in range(10, 24)},
        weather="rain",
        event="none",
        reason="full closure",
    )
    forecaster.apply_correction(
        "2025-08-03",
        {hour: 1000 for hour in range(10, 24)},
        weather="rain",
        event="none",
        reason="unexpected festival spillover",
    )

    rain_factor = forecaster.state["weather_factors"]["rain"]
    none_event_factor = forecaster.state["event_factors"]["none"]
    shape_total = sum(float(value) for value in forecaster.state["hourly_shape"].values())

    assert 0.45 <= rain_factor <= 1.9
    assert 0.45 <= none_event_factor <= 1.9
    assert shape_total == pytest.approx(1.0, abs=0.001)
