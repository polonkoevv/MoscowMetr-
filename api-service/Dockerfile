FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY api-service/pyproject.toml .
RUN uv pip install --system --no-cache .

# Папка для логов
RUN mkdir -p /app/logs

# Данные и метрики
COPY data/listings.parquet /app/data/listings.parquet
COPY ml-service/artifacts/metrics.json /app/data/metrics.json

# Код сервиса
COPY api-service/main.py ./
COPY api-service/app/ ./app/
COPY api-service/alembic/ ./alembic/
COPY api-service/alembic.ini ./

EXPOSE 8000

# Сначала применяем миграции, потом стартуем сервер
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
