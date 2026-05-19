from fastapi import APIRouter, status, HTTPException, Depends
from ..services.subscription import SubscriptionService

subscription_router = APIRouter(prefix="/subscription", tags=["subscription"])
def get_subscription_service():
    return SubscriptionService()

# this endpoint is only for testing the function, will be deleted afterwards
@subscription_router.get("/{installation_uuid}")
async def check_subscription_status(installation_uuid, service: SubscriptionService = Depends(get_subscription_service)):
    response = await service.get_subscription_status(installation_uuid)
    return response
