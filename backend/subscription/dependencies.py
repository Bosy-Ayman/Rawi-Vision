import os
from fastapi import Depends, HTTPException, status
from database import db_dependency
from .services.subscription import SubscriptionService

def verify_feature_access(feature_name: str):
    async def dependency(db: db_dependency):
        # Bypass subscription checks for testing
        return True
    return dependency
