from pydantic import BaseModel, ConfigDict
from uuid import UUID

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    role: str  #must be changing to enum later on when the roles get defined.

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeResponse(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    embedding: list[float] | None = None

class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name:str | None = None
    role: str | None = None
    embedding: list[float] | None = None