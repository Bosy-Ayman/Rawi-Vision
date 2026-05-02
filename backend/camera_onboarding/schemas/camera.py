from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class CameraBase(BaseModel):
    room: str
    building: str
    mac_address: str
    username: str
    password: str

class CameraCreate(CameraBase):
    pass

class CameraResponse(CameraBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    password: str
    date_created: datetime