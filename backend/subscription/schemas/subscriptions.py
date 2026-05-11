from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional


class SubscriptionCreate(BaseModel):
    tenant_id: UUID
    installation_uuid: UUID
    plan_id: str
    subscription_type: str  # "monthly" | "annual"


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subscription_id: UUID
    state: str
    trial_ends_at: Optional[datetime]
    token: Optional[str] = None  # minted on creation and check-in


class SubscriptionStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subscription_id: UUID
    state: str
    token: Optional[str] = None


class CheckInRequest(BaseModel):
    installation_uuid: UUID
    token: str
    usage: dict  # arbitrary usage payload — store as-is


class CheckInResponse(BaseModel):
    status: str          # "ok" | "suspended" | "canceled" | "expired"
    token: Optional[str] = None
    message: Optional[str] = None
