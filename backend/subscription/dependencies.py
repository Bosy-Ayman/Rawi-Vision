import os
from fastapi import Depends, HTTPException, status
from database import db_dependency
from .services.subscription import SubscriptionService

def verify_feature_access(feature_name: str):
    async def dependency(db: db_dependency):
        # Retrieve local installation identifier from environment variable
        installation_uuid = os.getenv("INSTALLATION_UUID", "test_installation_id")
        service = SubscriptionService(db=db)
        has_access = await service.verify_feature_access(installation_uuid, feature_name)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Access to '{feature_name}' requires an upgraded active subscription plan."
            )
        return True
    return dependency
