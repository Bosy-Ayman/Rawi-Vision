from fastapi import APIRouter, status, HTTPException, Depends, Form
from ..schemas.subscriptions import SubscriptionCreate, SubscriptionResponse, SubscriptionStateResponse, CheckInRequest, CheckInResponse
from ..repository.subscriptions import SubscriptionsRepository
from ..repository.plans import PlansRepository
from ..services.subscriptions import SubscriptionsService
from ..utils.exceptions import SubscriptionNotFound, InvalidStateTransition, PlanNotFound
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

subscription_router = APIRouter(prefix='/subscriptions', tags=["subscriptions"])


async def get_subscription_repo(db: AsyncSession = Depends(get_db)):
    return SubscriptionsRepository(db=db)

async def get_plans_repo(db: AsyncSession = Depends(get_db)):
    return PlansRepository(db=db)

async def get_subscription_service(sub_repo: SubscriptionsRepository = Depends(get_subscription_repo), plans_repo: PlansRepository = Depends(get_plans_repo)):
    return SubscriptionsService(subscription_repo=sub_repo, plans_repo=plans_repo)


@subscription_router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(tenant_id: UUID = Form(...), installation_uuid: UUID = Form(...), plan_id: str = Form(...), subscription_type: str = Form(...), service: SubscriptionsService = Depends(get_subscription_service)):
    try:
        subscription_instance = SubscriptionCreate(tenant_id=tenant_id, installation_uuid=installation_uuid, plan_id=plan_id, subscription_type=subscription_type)
        sub, token = await service.create_subscription(subscription=subscription_instance)
        return SubscriptionResponse(subscription_id=sub.id, state=sub.state, trial_ends_at=sub.trial_ends_at, token=token,)
    except PlanNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as error:
        raise error

# call this when payment is confirmed, it set the billing cycle and issues a fresh token 
@subscription_router.post("/{subscription_id}/activate", response_model=SubscriptionStateResponse)
async def activate_subscription(subscription_id: UUID,service: SubscriptionsService = Depends(get_subscription_service)):
    try:
        sub, token = await service.activate(subscription_id)
        return SubscriptionStateResponse(subscription_id=sub.id, state=sub.state, token=token)
    except SubscriptionNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransition as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

# Moves active → past_due. Call this when a payment fails. The tenant's next check in will return a suspended signal.
@subscription_router.post("/{subscription_id}/past-due", response_model=SubscriptionStateResponse)
async def mark_past_due(subscription_id: UUID,service: SubscriptionsService = Depends(get_subscription_service)):
    try:
        sub, token = await service.mark_past_due(subscription_id)
        return SubscriptionStateResponse(subscription_id=sub.id, state=sub.state, token=token)
    except SubscriptionNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransition as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@subscription_router.post("/{subscription_id}/cancel", response_model=SubscriptionStateResponse)
async def cancel_subscription(subscription_id: UUID,service: SubscriptionsService = Depends(get_subscription_service)):
    try:
        sub = await service.cancel(subscription_id)
        return SubscriptionStateResponse(subscription_id=sub.id, state=sub.state)
    except SubscriptionNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransition as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@subscription_router.post("/{subscription_id}/expire", response_model=SubscriptionStateResponse)
async def expire_subscription(subscription_id: UUID, service: SubscriptionsService = Depends(get_subscription_service)):
    try:
        sub = await service.expire(subscription_id)
        return SubscriptionStateResponse(subscription_id=sub.id, state=sub.state)
    except SubscriptionNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransition as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@subscription_router.patch("/{subscription_id}/plan", response_model=SubscriptionStateResponse)
async def change_plan(subscription_id: UUID, new_plan_id: str, service: SubscriptionsService = Depends(get_subscription_service)):
    try:
        sub, token = await service.change_plan(subscription_id, new_plan_id)
        return SubscriptionStateResponse(subscription_id=sub.id, state=sub.state, token=token)
    except (SubscriptionNotFound, PlanNotFound) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransition as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# Check-in  (called by tenant agents)
@subscription_router.post("/check-in", response_model=CheckInResponse, status_code=status.HTTP_200_OK)
async def check_in(request: CheckInRequest, service: SubscriptionsService = Depends(get_subscription_service)):
    try:
        result = await service.check_in(request)
        return CheckInResponse(**result)
    except Exception as error:
        raise error
