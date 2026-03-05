from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime
from ..models.system_user import SystemRole


class SystemUserCreate(BaseModel):
    """Used by SuperAdmin to whitelist a new HR or Manager."""
    email: EmailStr
    full_name: str
    role: SystemRole


class SystemUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str
    role: SystemRole
    date_created: datetime


class GoogleLoginRequest(BaseModel):
    """Frontend sends the Google id_token here."""
    id_token: str


class TokenResponse(BaseModel):
    """Returned after a successful Google login."""
    access_token: str
    token_type: str = "bearer"
    role: SystemRole
    full_name: str
