FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-dev.txt

COPY data ./data
COPY docs ./docs
COPY scripts ./scripts
COPY src ./src
COPY tests ./tests
COPY main.py README.md SAMPLE_OUTPUT.md pyproject.toml ./

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
