from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://admin:secret@postgres:5432/du_portal_diploma"

    # JWT
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30       # 30 минут
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30         # 30 дней

    # ML Service
    ML_SERVICE_URL: str = "http://ml-service:8001"

    # Parquet
    LISTINGS_PATH: str = "/app/data/listings.parquet"

    # Первый admin (создаётся при старте если нет ни одного)
    ADMIN_EMAIL:    str = "admin@reval.ru"
    ADMIN_PASSWORD: str = "changeme"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    PREDICT_CACHE_TTL: int = 60 * 60        # 1 час
    STATS_CACHE_TTL:   int = 60 * 30        # 30 минут

    # CORS — список разрешённых источников через запятую
    # Пример: "http://localhost:3000,https://reval.ru"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8501"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
