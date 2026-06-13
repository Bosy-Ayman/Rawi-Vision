from fastapi import APIRouter, status, HTTPException, Depends
from pydantic import BaseModel
from database import db_dependency
from ..services.subscription import SubscriptionService
from ..utils.redis import redis_client
from ..models.license import LicenseInfo
from sqlalchemy.future import select
import json
import logging

logger = logging.getLogger(__name__)
subscription_router = APIRouter(prefix="/subscription", tags=["subscription"])

class WebhookSubscriptionUpdate(BaseModel):
    installation_uuid: str
    status: str
    tier: str
    signature: str | None = None

def get_subscription_service(db: db_dependency):
    return SubscriptionService(db=db)

@subscription_router.get("/installation-id/config")
async def get_configured_installation_uuid():
    import os
    return {"installation_uuid": os.getenv("INSTALLATION_UUID", "test_installation_id")}

@subscription_router.get("/{installation_uuid}")
async def check_subscription_status(
    installation_uuid: str, 
    service: SubscriptionService = Depends(get_subscription_service)
):
    try:
        response = await service.get_subscription_status(installation_uuid)
        return response
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Subscription check failed: {str(err)}"
        )

@subscription_router.post("/webhook/update", status_code=status.HTTP_200_OK)
async def receive_subscription_webhook(
    payload: WebhookSubscriptionUpdate,
    db: db_dependency,
    service: SubscriptionService = Depends(get_subscription_service)
):
    try:
        logger.info(f"Received subscription webhook update: {payload.model_dump()}")
        
        # 1. Signature Verification Placeholder
        # In production, check: HMAC-SHA256 signature using WEBHOOK_SECRET_KEY
        
        # 2. Update local database
        stmt = select(LicenseInfo).where(LicenseInfo.installation_uuid == payload.installation_uuid)
        result = await db.execute(stmt)
        license_record = result.scalars().first()
        
        if license_record:
            license_record.status = payload.status
            license_record.tier = payload.tier
        else:
            new_license = LicenseInfo(
                installation_uuid=payload.installation_uuid,
                status=payload.status,
                tier=payload.tier
            )
            db.add(new_license)
        await db.commit()
        
        # 3. Update Redis cache immediately so UI/API changes take effect instantly
        mapped_data = service.map_tier_to_features(payload.status, payload.tier)
        await redis_client.set(f"{payload.installation_uuid}", json.dumps(mapped_data), ex=86400)
        
        return {"status": "success", "message": "Local subscription status updated successfully"}
    except Exception as err:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(err)}"
        )
