from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AnomalyTypeEnum(str, Enum):
    VIOLENCE = "violence"
    THEFT = "theft"
    VANDALISM = "vandalism"
    UNUSUAL_BEHAVIOR = "unusual_behavior"
    OUT_OF_BOUNDS = "out_of_bounds"
    UNKNOWN = "unknown"


class AnomalyBase(BaseModel):
    anomaly_type: AnomalyTypeEnum = AnomalyTypeEnum.UNKNOWN
    description: str = Field(..., max_length=1000)
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    camera_id: str = Field("default", max_length=100)
    image_url: Optional[str] = Field(None, max_length=500)
    employee_id: Optional[str] = Field(None, max_length=100)


class AnomalyCreate(AnomalyBase):
    """Used internally when creating a new anomaly (from Kafka event)."""
    pass


class AnomalyResponse(AnomalyBase):
    """Returned to the frontend."""
    id: int
    detected_at: datetime

    class Config:
        from_attributes = True
