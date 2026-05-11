from pydantic import BaseModel
from uuid import UUID

class LicenseTokenPayload(BaseModel):
    installation_uuid: UUID
    tenant_id: UUID
    plan_id: str
    subscription_state: str
    subscription_type: str
    entitlements: dict
