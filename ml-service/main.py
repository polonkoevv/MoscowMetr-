"""
ML Service — сервис предсказания цены недвижимости.
Запуск локально: uvicorn main:app --port 8001 --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from schemas import PredictRequest, PredictResponse, HealthResponse
from predictor import PricePredictor

# --- Глобальный предиктор, загружается один раз при старте ---
predictor: PricePredictor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global predictor
    print("Загрузка модели...")
    predictor = PricePredictor()
    print(f"Модель загружена. Best iteration: {predictor.best_iteration}")
    yield
    print("ML Service остановлен.")


app = FastAPI(
    title="ML Service — Price Predictor",
    description="Внутренний сервис предсказания цен на недвижимость. Не требует авторизации — доступен только внутри Docker-сети.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Проверка состояния сервиса."""
    return HealthResponse(
        status="ok",
        model_loaded=predictor is not None,
        best_iteration=predictor.best_iteration if predictor else None,
    )


@app.post("/predict", response_model=PredictResponse, tags=["Prediction"])
def predict(request: PredictRequest):
    """
    Предсказание цены объекта недвижимости.

    Принимает характеристики объекта, возвращает:
    - `price` — предсказанная цена, руб.
    - `price_per_m2` — цена за м², руб/м²
    - `mape` — ожидаемая погрешность модели, %
    - `okrug` — округ Москвы (если определён по координатам)
    """
    if predictor is None:
        raise HTTPException(status_code=503, detail="Модель не загружена")
    return predictor.predict(request)
