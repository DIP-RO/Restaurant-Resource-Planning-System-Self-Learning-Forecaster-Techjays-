# Model Card

## Model Choice

This project uses an explainable coefficient-based demand forecaster, not a deep learning model.

As an AI engineering decision, this is the right model for the assignment because:

- The dataset is small and tabular.
- Restaurant managers need to understand why a prediction changed.
- The system must learn from explicit manager corrections.
- The output drives operational decisions, so debuggability matters more than black-box accuracy.

The forecaster behaves like a lightweight online learning model:

```text
daily_demand =
base_daily_average
× weekday_factor
× weather_factor
× event_factor
× holiday_factor
```

The daily demand is then distributed across service hours using a learned hourly demand curve.

## Why Train?

Training is needed to learn the starting coefficients from historical data instead of hard-coding assumptions.

During initial training, the system calculates:

- Average daily covers.
- Weekday factors, such as Friday being busier than Monday.
- Weather factors, such as rain reducing walk-ins.
- Event factors, such as concerts increasing demand.
- Hourly demand distribution across lunch and dinner.
- Menu mix from historical dish demand.

After initial training, manager corrections continue the learning loop. If the model predicts 120 covers and actual covers are 85 because of rain, the rain coefficient is reduced. Future rainy-day forecasts become lower.

## Preprocessing

The preprocessing is intentionally simple and auditable:

1. Parse CSV rows from `data/sales_history.csv`.
2. Convert numeric fields such as `hour`, `covers`, and `dish_orders`.
3. Group rows by date to calculate daily totals.
4. Group daily totals by weekday, weather, and event.
5. Normalize each group average against the base daily average to create factors.
6. Normalize hourly cover totals so all hourly shares sum to 1.0.
7. Normalize dish order counts into a menu mix distribution.

No target leakage is used. Future dates are forecast using only the learned coefficients and the provided date context.

## Feedback Update

Manager corrections use bounded online updates:

```text
ratio = actual_total / predicted_total
multiplier_delta = 1 + ((ratio - 1) × learning_rate)
new_factor = old_factor × multiplier_delta
```

The update is bounded so a single unusual night cannot destroy the model. The hourly distribution is also nudged toward the actual hour-by-hour pattern.

## Why Not Use Deep Learning?

A neural network or large time-series model would be excessive here:

- The generated dataset is small.
- The assignment asks for clear business logic and a feedback loop.
- Deep models are harder to explain in an operational planning interview.
- This system needs to be easy to inspect, test, and extend.

In a production restaurant group with years of POS data, this design could evolve into gradient boosted trees, Prophet-style time-series components, or hierarchical forecasting. The current version is deliberately practical and transparent.

## Runtime Efficiency

The production path is lightweight:

- No external runtime libraries.
- Historical CSVs are loaded once per `RestaurantForecaster` instance.
- Forecasting only multiplies learned factors and applies a fixed hourly distribution.
- Staffing is rule-based and linear in the number of service hours and roles.
- Ingredient planning is linear in menu recipes and ingredient count.
- Feedback learning updates existing coefficients online instead of retraining the full model.

This keeps the system easy to run in Docker, easy to inspect in code review, and fast enough for operational planning.
