# Restaurant Resource Planning System - Self-Learning Forecaster

![CI](https://github.com/DIP-RO/Restaurant-Resource-Planning-System-Self-Learning-Forecaster-Techjays-/actions/workflows/ci.yml/badge.svg)

This repository contains a production-style Python solution for restaurant resource planning. It forecasts hourly customer covers, converts those covers into staffing requirements, estimates ingredient orders from menu recipes, and learns from manager corrections after service.

The project is intentionally built as an explainable AI engineering system instead of a notebook or black-box model. Restaurant managers must be able to understand why a rainy Friday forecast changed, why extra staff are needed at 7 PM, and why the system recommends ordering more chicken before a supplier cutoff.

## What The System Predicts

The system produces three operational outputs for an upcoming day:

- Hourly customer covers from 10:00 to 23:00.
- Staff count by role for each hour.
- Ingredient order plan with required quantity, current stock, order quantity, shelf life, and supplier lead time.

It also accepts manager feedback, such as "we predicted 120 covers, but actual was 85 because of rain", and updates the model coefficients so future similar forecasts improve.

## Why This Modeling Approach

For this assignment, I used an explainable coefficient-based online learning forecaster.

I did not use deep learning because the problem has a small tabular dataset, clear business drivers, and a required feedback loop. A neural network would be harder to explain, harder to debug, and unnecessary for this data size. In a restaurant planning workflow, interpretability is a feature: managers need to trust the output before using it for staffing and purchasing.

The selected model is appropriate because:

- It learns from historical data rather than hard-coded guesses.
- It produces transparent factors for weekday, weather, events, holidays, and hourly demand shape.
- It supports online learning from manager corrections.
- It is simple to test, inspect, and extend.
- It is safe for operational planning because coefficient updates are bounded.

## Forecasting Model

The model estimates daily demand, then distributes that demand across service hours.

```text
predicted_daily_covers =
base_daily_average
* weekday_factor
* weather_factor
* event_factor
* holiday_factor
```

Then:

```text
predicted_hourly_covers =
predicted_daily_covers * learned_hourly_distribution[hour]
```

Example:

```text
Base daily average = 110 covers
Friday factor = 1.25
Rain factor = 0.75
Concert factor = 1.20

Predicted daily covers = 110 * 1.25 * 0.75 * 1.20 = 123.75
```

The hourly distribution then allocates those covers across lunch and dinner peaks.

## Why Training Is Needed

Training is used to learn the initial coefficients from historical CSV data.

During training, the system calculates:

- Base daily average covers.
- Weekday factors from daily totals grouped by weekday.
- Weather factors from daily totals grouped by weather.
- Event factors from daily totals grouped by event type.
- Hourly service shape from historical hourly cover distribution.
- Menu mix from historical dish order counts.

This means the model starts from observed restaurant behavior instead of fixed assumptions. After deployment, manager corrections continue improving the model.

## Preprocessing

The preprocessing pipeline is intentionally auditable:

1. Read `data/sales_history.csv`.
2. Parse numeric columns such as `hour`, `covers`, and `dish_orders`.
3. Aggregate hourly rows into daily totals.
4. Group daily totals by weekday, weather, and event.
5. Normalize each group average against the base daily average.
6. Normalize hourly cover totals so hourly shares sum to 1.0.
7. Normalize dish orders into a menu mix distribution.

No future information is used when forecasting an upcoming date.

## Feedback Learning

Manager corrections update coefficients after actual service results are known.

```text
ratio = actual_total / predicted_total
multiplier_delta = 1 + ((ratio - 1) * learning_rate)
new_factor = old_factor * multiplier_delta
```

If actual covers are lower than predicted on a rainy day, the rain coefficient decreases. Future rainy-day forecasts become lower. The hourly demand shape is also nudged toward the actual hourly pattern.

Updates are bounded so one unusual night cannot destroy the model.

## Architecture

```text
data/
  sales_history.csv          Historical generated demand data
  menu_recipes.csv           Dish-to-ingredient recipe mapping
  ingredients.csv            Current stock, shelf life, lead time, min order qty
  staff_rules.csv            Role-based staffing thresholds
  manager_corrections.csv    Example correction records

scripts/
  generate_dataset.py        Deterministic synthetic dataset generator
  evaluate_model.py          Forecast error evaluation report

src/restaurant_forecaster/
  forecaster.py              Main model coordinator and online learning loop
  staffing.py                Staffing rule engine
  inventory.py               Ingredient planning engine
  feedback.py                Coefficient update math
  cli.py                     Command-line entry point

main.py                      Simple root runner for reviewers

docs/
  MODEL_CARD.md              Model choice, preprocessing, and learning details

tests/
  test_forecaster.py         Unit tests for forecast, inventory, feedback, validation

requirements.txt             Runtime requirements; intentionally empty
requirements-dev.txt         Test/development requirements
```

### Component Responsibilities

- `forecaster.py`: trains the initial model, predicts covers, coordinates staffing and inventory, applies corrections.
- `staffing.py`: converts hourly covers into role counts using business rules.
- `inventory.py`: converts predicted covers and menu mix into ingredient order quantities.
- `feedback.py`: contains bounded update functions for online learning.
- `cli.py`: provides the runnable interface for forecast and correction commands.

## Staffing Logic

Staffing rules are stored in `data/staff_rules.csv`.

Examples:

- 1 server per 18 covers per hour.
- 1 line cook per 22 covers per hour.
- 1 dishwasher per 40 covers per hour.
- 1 manager whenever the restaurant is open.

This keeps labor planning explainable and easy to adjust for a real restaurant.

## Ingredient Planning Logic

The system predicts total covers, estimates dish demand from learned menu mix, then expands dish demand into ingredients using `menu_recipes.csv`.

```text
expected covers = 100
burger menu share = 30%
burger demand = 30

1 burger requires:
- 1 bun
- 0.18 kg beef

30 burgers require:
- 30 buns
- 5.4 kg beef
```

Order quantity:

```text
order_quantity = max(required_quantity * safety_buffer - current_stock, minimum_order_quantity)
```

The final order output includes supplier lead time and the date by which the ingredient must be ordered.

## Run The Project

### Docker

Build the image:

```bash
docker build -t restaurant-forecaster .
```

Run a forecast:

```bash
docker run --rm restaurant-forecaster forecast --date 2025-08-01 --weather rain --event concert
```

Apply manager feedback:

```bash
docker run --rm restaurant-forecaster correct \
  --date 2025-08-01 \
  --weather rain \
  --event concert \
  --actual '{"10":2,"11":5,"12":12,"13":10,"14":6,"15":4,"16":5,"17":8,"18":13,"19":15,"20":12,"21":7,"22":3,"23":1}' \
  --reason "Heavy rain reduced walk-ins"
```

Run tests inside Docker:

```bash
docker run --rm --entrypoint python restaurant-forecaster -m pytest -q
```

Run model evaluation inside Docker:

```bash
docker run --rm --entrypoint python restaurant-forecaster scripts/evaluate_model.py
```

### Local Python

Generate or refresh the sample data:

```bash
python scripts/generate_dataset.py
```

Run a forecast:

```bash
PYTHONPATH=src python main.py forecast --date 2025-08-01 --weather rain --event concert
```

Equivalent package command:

```bash
PYTHONPATH=src python -m restaurant_forecaster.cli forecast --date 2025-08-01 --weather rain --event concert
```

Apply manager feedback:

```bash
PYTHONPATH=src python main.py correct \
  --date 2025-08-01 \
  --weather rain \
  --event concert \
  --actual '{"10":2,"11":5,"12":12,"13":10,"14":6,"15":4,"16":5,"17":8,"18":13,"19":15,"20":12,"21":7,"22":3,"23":1}' \
  --reason "Heavy rain reduced walk-ins"
```

Equivalent package command:

```bash
PYTHONPATH=src python -m restaurant_forecaster.cli correct \
  --date 2025-08-01 \
  --weather rain \
  --event concert \
  --actual '{"10":2,"11":5,"12":12,"13":10,"14":6,"15":4,"16":5,"17":8,"18":13,"19":15,"20":12,"21":7,"22":3,"23":1}' \
  --reason "Heavy rain reduced walk-ins"
```

Run tests:

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest -v
```

Evaluate model error on the generated dataset:

```bash
python scripts/evaluate_model.py
```

## Validation

The test suite checks:

- Forecast output contains covers, staffing, and ingredient orders.
- Weather and event factors change forecasted demand.
- High on-hand stock can eliminate ingredient orders.
- Manager correction lowers the relevant coefficient when actual demand is lower.
- Learned correction state persists and reloads.
- Invalid service hours are rejected.
- Negative actual covers are rejected.
- Negative on-hand stock is rejected.
- Unknown weather and event labels are rejected.
- Evaluation script reports MAE, RMSE, and MAPE for forecast error.

Full test output is included in [SAMPLE_OUTPUT.md](SAMPLE_OUTPUT.md).

## Production Notes

The current implementation is intentionally lightweight and dependency-free at runtime. In production, I would add:

- POS integration for real historical sales.
- Weather API integration.
- Local event calendar integration.
- Reservation and walk-in split.
- Role-specific labor constraints and shift length rules.
- Supplier calendars and order cutoff times.
- Model monitoring for forecast error by weekday, weather, and event.

The architecture is already separated so these upgrades can be added without rewriting the core forecasting loop.

## CI/CD

GitHub Actions is configured in `.github/workflows/ci.yml`.

The pipeline runs on pushes and pull requests to `main`:

- Installs development dependencies.
- Runs the Python test suite.
- Runs the model evaluation script.
- Builds the Docker image.
- Smoke-tests the Docker forecast command.
- Runs tests and model evaluation inside Docker.
