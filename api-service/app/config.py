from pydantic import field_validator, model_validator
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
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8501"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Валидаторы ────────────────────────────────────────────────

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_not_default(cls, v: str) -> str:
        if v == "change-me":
            raise ValueError("SECRET_KEY не может быть 'change-me' — задайте случайный ключ в переменных окружения")
        if len(v) < 32:
            raise ValueError("SECRET_KEY должен быть не короче 32 символов")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_valid(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL должен начинаться с 'postgresql+asyncpg://'")
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def redis_url_valid(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL должен начинаться с 'redis://' или 'rediss://'")
        return v

    @field_validator("ML_SERVICE_URL")
    @classmethod
    def ml_service_url_valid(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("ML_SERVICE_URL должен быть корректным HTTP URL")
        return v

    @field_validator("ADMIN_PASSWORD")
    @classmethod
    def admin_password_not_default(cls, v: str) -> str:
        if v == "changeme":
            raise ValueError("ADMIN_PASSWORD не может быть 'changeme' — задайте надёжный пароль")
        if len(v) < 8:
            raise ValueError("ADMIN_PASSWORD должен быть не короче 8 символов")
        return v

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def access_token_expire_positive(cls, v: int) -> int:
        if v < 5:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES должен быть не менее 5 минут")
        return v

    @model_validator(mode="after")
    def cors_origins_not_empty(self) -> "Settings":
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS не может быть пустым")
        return self


settings = Settings()
