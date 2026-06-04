import httpx
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..utils.redis import redis_client
from ..models.license import LicenseInfo

logger = logging.getLogger(__name__)

class SubscriptionService:
    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.developer_app_server_url = "http://localhost:8001"

    def map_tier_to_features(self, status: str, tier: str):
        normalized_status = "active" if status in ("active", "ok") else status
        if normalized_status != "active":
            return {
                "status": normalized_status,
                "message": f"Subscription {normalized_status}",
                "attendance": False,
                "search": False,
                "summarization": False
            }
        
        if tier == "0":
            return {"status": "active", "message": "Subscription active", "attendance": True, "search": False, "summarization": False}
        elif tier == "1":
            return {"status": "active", "message": "Subscription active", "attendance": True, "search": True, "summarization": False}
        elif tier == "2":
            return {"status": "active", "message": "Subscription active", "attendance": True, "search": True, "summarization": True}
        
        return {"status": "active", "message": "Subscription active", "attendance": True, "search": False, "summarization": False}

    async def get_subscription_status(self, installation_uuid: str):
        url = f"{self.developer_app_server_url}/subscriptions/check-in/{installation_uuid}"
        subscription_data = None
        
        # 1. Try to contact the central developer billing server
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url)
            if response.status_code == 200:
                subscription_data = response.json()
                # Store the updated state in Redis cache with an expiry of 24 hours
                await redis_client.set(f"{installation_uuid}", json.dumps(subscription_data), ex=86400)
                
                # Sync status to the local database if DB session is available
                if self.db:
                    stmt = select(LicenseInfo).where(LicenseInfo.installation_uuid == installation_uuid)
                    result = await self.db.execute(stmt)
                    license_record = result.scalars().first()
                    
                    status_val = subscription_data.get("status", "active")
                    # Deduce tier based on active features
                    tier_val = "0"
                    if subscription_data.get("summarization"):
                        tier_val = "2"
                    elif subscription_data.get("search"):
                        tier_val = "1"
                        
                    if license_record:
                        license_record.status = status_val
                        license_record.tier = tier_val
                    else:
                        new_license = LicenseInfo(
                            installation_uuid=installation_uuid,
                            status=status_val,
                            tier=tier_val
                        )
                        self.db.add(new_license)
                    await self.db.commit()
                return subscription_data
        except Exception as err:
            logger.warning(f"Failed to check-in with central billing server: {err}. Falling back to cache/local database.")

        # 2. Fallback to Redis Cache
        cached_data = await redis_client.get(installation_uuid)
        if cached_data:
            return json.loads(cached_data)

        # 3. Fallback to Local SQLite/Postgres Database
        if self.db:
            stmt = select(LicenseInfo).where(LicenseInfo.installation_uuid == installation_uuid)
            result = await self.db.execute(stmt)
            license_record = result.scalars().first()
            if license_record:
                mapped_data = self.map_tier_to_features(license_record.status, license_record.tier)
                # Populate Redis cache for quick lookup in subsequent calls
                await redis_client.set(f"{installation_uuid}", json.dumps(mapped_data), ex=3600)
                return mapped_data

        # 4. Default Blocked State if no records exist anywhere and server is down
        fallback_data = {"status": "suspended", "message": "No local license registered and subscription server offline", "attendance": False, "search": False, "summarization": False}
        return fallback_data

    async def verify_feature_access(self, installation_uuid: str, feature_name: str) -> bool:
        # Check cache first for high speed
        cached_data = await redis_client.get(installation_uuid)
        if cached_data:
            data = json.loads(cached_data)
        else:
            try:
                data = await self.get_subscription_status(installation_uuid)
            except Exception:
                return False
        
        status = data.get("status")
        if status not in ("active", "ok"):
            return False
            
        return bool(data.get(feature_name, False))
