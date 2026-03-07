from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class AnomalyBase(BaseModel):
    # TODO: Define common fields for Anomaly
    pass

class AnomalyCreate(AnomalyBase):
    # TODO: Define fields required for creation from Kafka/AI
    pass

class AnomalyResponse(AnomalyBase):
    # TODO: Define fields for API response including IDs
    pass
