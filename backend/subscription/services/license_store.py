import os
import httpx
from datetime import datetime, timezone
from uuid import UUID
from ..repository.license_store import LicenseStoreRepository
from ..services.license import LicenseService
from ..utils.exceptions import LicenseNotFound, LicenseInvalid

class LicenseStoreService:
    def __init__(self, repo: LicenseStoreRepository):
        self.repo = repo
        self.license_service = LicenseService()
        self.CHECKIN_URL = os.getenv("LICENSOR_CHECKIN_URL", "http://localhost:8000/subscriptions/check-in")
        # Grace period: how long the tenant app stays operational after token expiry
        self.GRACE_PERIOD_HOURS = int(os.getenv("LICENSE_GRACE_PERIOD_HOURS", "72"))

    def _decode_safe(self, token: str):
        try:
            return self.license_service.decode_token(token)
        except Exception:
            return None

    def _is_within_grace(self, claims: dict) -> bool:
        from datetime import timedelta
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        grace_deadline = exp + timedelta(hours=self.GRACE_PERIOD_HOURS)
        return datetime.now(timezone.utc) <= grace_deadline


    async def register_token(self, installation_uuid: UUID, token: str):
        try:
            claims = self._decode_safe(token)
            if not claims:
                raise LicenseInvalid("Token signature is invalid")
            if str(installation_uuid) != claims.get("installation_uuid"):
                raise LicenseInvalid("Token was not issued for this installation")
            store = await self.repo.upsert_token(installation_uuid, token)
            return store
        except Exception as error:
            raise error

    async def validate(self, installation_uuid: UUID):
        try:
            store = await self.repo.get_by_installation_uuid(installation_uuid)
            if not store:
                raise LicenseNotFound("No license found for this installation")
            claims = self._decode_safe(store.token)
            # Signature completely invalid — hard block
            if not claims:
                raise LicenseInvalid("Token signature is invalid")
            # Installation binding
            if str(installation_uuid) != claims.get("installation_uuid"):
                raise LicenseInvalid("Token was not issued for this installation")
            # Subscription state check — suspended/canceled/expired are hard blocks
            state = claims.get("subscription_state")
            if state in ("canceled", "expired"):
                raise LicenseInvalid(f"Subscription is {state}")
            if state == "past_due":
                raise LicenseInvalid("Subscription payment is overdue")
            # Expiry — allow grace period
            exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
            now = datetime.now(timezone.utc)
            is_expired = now > exp
            if is_expired and not self._is_within_grace(claims):
                raise LicenseInvalid("License has expired and grace period has elapsed")
            return {
                "installation_uuid": installation_uuid,
                "plan_id": claims["plan_id"],
                "subscription_state": state,
                "subscription_type": claims["subscription_type"],
                "entitlements": claims.get("entitlements", {}),
                "token_expires_at": exp,
                "is_valid": True,
            }
        except (LicenseNotFound, LicenseInvalid):
            raise
        except Exception as error:
            raise error

    async def perform_check_in(self, installation_uuid: UUID, usage: dict):
        store = await self.repo.get_by_installation_uuid(installation_uuid)
        if not store:
            raise LicenseNotFound("No license found for this installation")
        payload = {
            "installation_uuid": str(installation_uuid),
            "token": store.token,
            "usage": usage,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self.CHECKIN_URL, json=payload)
                response.raise_for_status()
                data = response.json()
            status = data.get("status")
            fresh_token = data.get("token")
            if status == "ok" and fresh_token:
                await self.repo.upsert_token(installation_uuid, fresh_token)
            await self.repo.log_check_in(installation_uuid, status, data.get("message"))
            return data
        except httpx.HTTPError as e:
            # network failure
            await self.repo.log_check_in(installation_uuid, "failed", str(e))
            return {"status": "failed", "message": "Check-in unreachable — running on grace period"}
