.PHONY: forecast correct test evaluate docker-build docker-forecast docker-test docker-evaluate compose-forecast compose-unseen compose-correct compose-test compose-evaluate clean

forecast:
	PYTHONPATH=src python main.py forecast --date 2025-08-01 --weather rain --event concert

correct:
	PYTHONPATH=src python main.py correct --date 2025-08-01 --weather rain --event concert --actual '{"10":2,"11":5,"12":12,"13":10,"14":6,"15":4,"16":5,"17":8,"18":13,"19":15,"20":12,"21":7,"22":3,"23":1}' --reason "Heavy rain reduced walk-ins"

test:
	PYTHONPATH=src python -m pytest -q

evaluate:
	python scripts/evaluate_model.py

docker-build:
	docker build -t restaurant-forecaster .

docker-forecast:
	docker run --rm restaurant-forecaster forecast --date 2025-08-01 --weather rain --event concert

docker-test:
	docker run --rm --entrypoint python restaurant-forecaster -m pytest -q

docker-evaluate:
	docker run --rm --entrypoint python restaurant-forecaster scripts/evaluate_model.py

compose-forecast:
	docker compose run --rm forecast

compose-unseen:
	docker compose run --rm forecast-unseen

compose-correct:
	docker compose run --rm correct

compose-test:
	docker compose run --rm test

compose-evaluate:
	docker compose run --rm evaluate

clean:
	rm -rf .pytest_cache .model_state.json src/restaurant_forecaster/__pycache__ tests/__pycache__
