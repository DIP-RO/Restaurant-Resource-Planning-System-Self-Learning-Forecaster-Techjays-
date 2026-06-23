# Sample Output And Test Results

## Forecast Command

```bash
docker run --rm restaurant-forecaster forecast --date 2025-08-03 --weather clear --event sports
```

Local equivalent:

```bash
PYTHONPATH=src python main.py forecast --date 2025-08-03 --weather clear --event sports
```

The forecast command returns JSON with:

- `covers_by_hour`: predicted covers for each service hour from 10 to 23.
- `staffing_by_hour`: role counts for each hour.
- `ingredient_order`: required quantity, current stock, order quantity, order-by date, supplier lead time, and shelf life.

## Correction Command

```bash
docker run --rm restaurant-forecaster correct --date 2025-08-01 --weather rain --event concert --actual '{"10":2,"11":5,"12":12,"13":10,"14":6,"15":4,"16":5,"17":8,"18":13,"19":15,"20":12,"21":7,"22":3,"23":1}' --reason "Heavy rain reduced walk-ins"
```

Local equivalent:

```bash
PYTHONPATH=src python main.py correct --date 2025-08-01 --weather rain --event concert --actual '{"10":2,"11":5,"12":12,"13":10,"14":6,"15":4,"16":5,"17":8,"18":13,"19":15,"20":12,"21":7,"22":3,"23":1}' --reason "Heavy rain reduced walk-ins"
```

Example correction summary:

```json
{
  "predicted_total": 129.2,
  "actual_total": 103.0,
  "adjustment_ratio": 0.797,
  "updated_weather_factor": 0.794,
  "updated_event_factor": 1.177,
  "message": "Model coefficients updated from manager correction."
}
```

## Test Command

```bash
docker build -t restaurant-forecaster .
docker run --rm --entrypoint python restaurant-forecaster -m pytest -q
```

Makefile equivalent:

```bash
make docker-build
make docker-test
```

Local equivalent:

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest -v
```

Docker Compose equivalent:

```bash
docker compose run --rm test
```

## Evaluation Command

```bash
docker run --rm --entrypoint python restaurant-forecaster scripts/evaluate_model.py
```

Local equivalent:

```bash
python scripts/evaluate_model.py
```

Docker Compose equivalent:

```bash
docker compose run --rm evaluate
```

Example evaluation output:

```json
{
  "days_evaluated": 210.0,
  "mae": 8.517,
  "rmse": 12.845,
  "mape_percent": 7.776
}
```

## Full Test Output

Docker test output:

```text
.....................                                                    [100%]
21 passed in 0.20s
```

Detailed local test output:

```text
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-8.4.2, pluggy-1.6.0 -- /opt/homebrew/opt/python@3.13/bin/python3.13
cachedir: .pytest_cache
rootdir: /Users/dipro/Techjys
configfile: pyproject.toml
plugins: asyncio-1.2.0, langsmith-0.4.28, anyio-4.10.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 21 items

tests/test_forecaster.py::test_forecast_includes_covers_staffing_and_ingredients PASSED [  4%]
tests/test_forecaster.py::test_correction_updates_future_weather_factor PASSED [  9%]
tests/test_forecaster.py::test_weather_and_event_context_change_cover_forecast PASSED [ 14%]
tests/test_forecaster.py::test_high_on_hand_stock_can_eliminate_ingredient_orders PASSED [ 19%]
tests/test_forecaster.py::test_correction_persists_and_reloads_model_state PASSED [ 23%]
tests/test_forecaster.py::test_invalid_correction_hour_is_rejected PASSED [ 28%]
tests/test_forecaster.py::test_negative_actual_covers_are_rejected PASSED [ 33%]
tests/test_forecaster.py::test_negative_on_hand_stock_is_rejected PASSED [ 38%]
tests/test_forecaster.py::test_weather_alias_is_normalized PASSED        [ 42%]
tests/test_forecaster.py::test_seen_weather_and_event_forecast_has_no_warnings PASSED [ 47%]
tests/test_forecaster.py::test_unseen_event_forecasts_with_learned_fallback_and_warning PASSED [ 52%]
tests/test_forecaster.py::test_unseen_weather_and_event_forecast_with_learned_fallbacks PASSED [ 57%]
tests/test_forecaster.py::test_unseen_event_correction_creates_learned_factor PASSED [ 61%]
tests/test_forecaster.py::test_unseen_weather_correction_creates_learned_factor PASSED [ 66%]
tests/test_forecaster.py::test_legacy_model_state_is_migrated_to_learned_fallbacks PASSED [ 71%]
tests/test_forecaster.py::test_unknown_on_hand_ingredient_is_rejected PASSED [ 76%]
tests/test_forecaster.py::test_empty_history_data_is_rejected PASSED     [ 80%]
tests/test_forecaster.py::test_history_missing_required_columns_is_rejected PASSED [ 85%]
tests/test_forecaster.py::test_corrupted_model_state_is_rejected PASSED  [ 90%]
tests/test_forecaster.py::test_incomplete_model_state_is_rejected PASSED [ 95%]
tests/test_forecaster.py::test_extreme_corrections_keep_coefficients_and_hourly_shape_bounded PASSED [100%]

============================== 21 passed in 0.13s ==============================
```

## What The Tests Prove

- The forecast pipeline returns all three required outputs.
- Weather and event signals influence predicted demand.
- Inventory planning respects available stock.
- Feedback learning updates coefficients.
- Model state can be saved and loaded.
- Invalid manager feedback is rejected instead of corrupting the model.
- Weather aliases are normalized.
- Seen weather and event labels forecast without warnings.
- Unseen weather and event labels forecast with learned fallback factors and warnings.
- Corrections for unseen labels create learned coefficients over time.
- Legacy model states are migrated to include learned fallback factors.
- Unknown ingredient names in stock input are rejected.
- Empty or malformed historical datasets are rejected with clear errors.
- Corrupted or incomplete model state files are rejected.
- Extreme corrections keep coefficients bounded and hourly shape normalized.
