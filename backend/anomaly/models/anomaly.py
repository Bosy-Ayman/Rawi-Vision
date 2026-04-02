import enum
from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from database import Base


class AnomalyType(str, enum.Enum):
    VIOLENCE = "violence"
    THEFT = "theft"
    VANDALISM = "vandalism"
    UNUSUAL_BEHAVIOR = "unusual_behavior"
    UNKNOWN = "unknown"


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_type: Mapped[AnomalyType] = mapped_column(
        SAEnum(AnomalyType, name="anomalytype"), nullable=False, default=AnomalyType.UNKNOWN
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    camera_id: Mapped[str] = mapped_column(String, nullable=False, default="default")
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Nullable: will be filled by face recognition module later
    employee_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
