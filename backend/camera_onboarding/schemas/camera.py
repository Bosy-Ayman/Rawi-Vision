from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class CameraBase(BaseModel):
    room: str
    building: str
    mac_address: str

class CameraCreate(CameraBase):
    pass

class CameraResponse(CameraBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    date_created: datetime