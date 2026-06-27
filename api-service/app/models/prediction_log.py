from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id:      Mapped[int]      = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    request_data: Mapped[dict]     = mapped_column(JSON, nullable=False)
    response_data: Mapped[dict]    = mapped_column(JSON, nullable=False)
    created_at:   Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
