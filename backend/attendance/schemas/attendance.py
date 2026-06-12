from pydantic import BaseModel, ConfigDict
from uuid import uuid4
from uuid import UUID
from datetime import date, datetime

class AttendanceBase(BaseModel):
    employee_id: UUID

class AttendanceCreate(AttendanceBase):
    camera_id: str | None = None
    duration_seconds: float = 0.0

class AttendanceResponse(AttendanceBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    day: date | None
    date_created: datetime | None
    last_seen: datetime | None
    look_count: int
    camera_id: str | None
    duration_seconds: float

class AttendanceWithEmployeeResponse(AttendanceResponse):
    first_name: str
    last_name: str
    role: str
    profile_image_url: str | None = None