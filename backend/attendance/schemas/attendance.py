from pydantic import BaseModel, ConfigDict
from uuid import uuid4
from uuid import UUID
from datetime import date, datetime

class AttendanceBase(BaseModel):
    employee_id: UUID

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceResponse(AttendanceBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    day: date | None
    date_created: datetime | None