import jwt
import uuid
from datetime import datetime, timezone, timedelta
from ..schemas.license import LicenseTokenPayload
import os  

# note that: private key should live here
class LicenseService:
    def __init__(self):
        self.SECRET_KEY = os.getenv("LICENSE_SECRET_KEY", "totallyspies") # needs to be set in env
        self.ALGORITHM = "HS256"
        self.TRIAL_TTL_DAYS = 14
        self.PAID_TTL_DAYS = 30 

    def mint_token(self, payload: LicenseTokenPayload):
        now = datetime.now(timezone.utc)

        if payload.subscription_state == "trial":
            ttl_days = self.TRIAL_TTL_DAYS
        else:
            ttl_days = self.PAID_TTL_DAYS

        claims = {
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(days=ttl_days),
            "installation_uuid": str(payload.installation_uuid),
            "tenant_id": str(payload.tenant_id),
            "plan_id": payload.plan_id,
            "subscription_state": payload.subscription_state,
            "subscription_type": payload.subscription_type,
            "entitlements": payload.entitlements,
        }
        token = jwt.encode(claims, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return token

    def decode_token(self, token: str):
        return jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
