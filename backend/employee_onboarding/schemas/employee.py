from pydantic import BaseModel, ConfigDict, Field
from fastapi import UploadFile
from uuid import UUID
from datetime import datetime
from typing import List

class EmployeeBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Za-z\s\-]+$")
    last_name: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Za-z\s\-]+$")
    role: str = Field(..., max_length=50)
    assigned_camera_ids: List[str] | None = None
    assigned_days: List[int] | None = Field(None, description="0=Monday, 6=Sunday")
    assigned_shift_start: str | None = Field(None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    assigned_shift_end: str | None = Field(None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

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
