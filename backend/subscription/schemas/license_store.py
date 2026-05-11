from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional

class LicenseStoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    installation_uuid: UUID
    token: str
    last_check_in_at: Optional[datetime]
    updated_at: datetime

class TokenRegisterRequest(BaseModel):
    installation_uuid: UUID
    token: str

class EntitlementsResponse(BaseModel):
    installation_uuid: UUID
    plan_id: str
    subscription_state: str
    subscription_type: str
    entitlements: dict
    token_expires_at: datetime
    is_valid: bool

class CheckInLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    installation_uuid: UUID
    status: str
    message: Optional[str]
    attempted_at: datetime
