import sys
from loguru import logger


def setup_logging() -> None:
    logger.remove()  # убираем дефолтный handler

    # Консоль — читаемый формат с цветами
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # Файл — все логи с ротацией
    logger.add(
        "/app/logs/app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} — {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )
