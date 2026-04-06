from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class AnomalyTypeEnum(str, Enum):
    VIOLENCE = "violence"
    THEFT = "theft"
    VANDALISM = "vandalism"
    UNUSUAL_BEHAVIOR = "unusual_behavior"
    UNKNOWN = "unknown"


class AnomalyBase(BaseModel):
    anomaly_type: AnomalyTypeEnum = AnomalyTypeEnum.UNKNOWN
    description: str
    confidence_score: float = 0.0
    camera_id: str = "default"
    image_url: Optional[str] = None
    employee_id: Optional[str] = None


class AnomalyCreate(AnomalyBase):
    """Used internally when creating a new anomaly (from Kafka event)."""
    pass


class AnomalyResponse(AnomalyBase):
    """Returned to the frontend."""
    id: int
    detected_at: datetime

    class Config:
        from_attributes = True
