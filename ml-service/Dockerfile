FROM python:3.12-slim

# Устанавливаем uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Артефакты модели
COPY artifacts/ /app/artifacts/

# Код сервиса
COPY main.py predictor.py schemas.py ./

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
