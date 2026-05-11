from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class TenantsBase(BaseModel):
    name: str
    phone_no: str
    contact_email: str
    access_email: str
    access_password: str


class TenantsCreate(TenantsBase):
    installation_uuid: UUID   


class TenantsResponse(TenantsBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    installation_uuid: UUID
    created_at: datetime

