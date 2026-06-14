from pydantic import BaseModel, ConfigDict
from fastapi import UploadFile
from uuid import UUID
from datetime import datetime
from typing import List

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    role: str  # must be changed to enum later on when the roles get defined.
    assigned_camera_ids: List[str] | None = None
    assigned_days: List[int] | None = None
    assigned_shift_start: str | None = None
    assigned_shift_end: str | None = None

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeResponse(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    date_created: datetime
    embedding: list[float] | None = None
    embedding_status : str
    images: List[str] | None = None 
    profile_image_url: str | None = None

class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name:str | None = None
    role: str | None = None
    embedding: list[float] | None = None
    embedding_status : str| None =  None
    assigned_camera_ids: List[str] | None = None
    assigned_days: List[int] | None = None
    assigned_shift_start: str | None = None
    assigned_shift_end: str | None = None
