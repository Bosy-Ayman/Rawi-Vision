from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..schemas.subscriptions import SubscriptionCreate
from ..models.subscriptions import Subscriptions
from ..models.usage_log import UsageLog
from datetime import datetime, timezone
import uuid

class SubscriptionsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_subscription(self, subscription: SubscriptionCreate, trial_ends_at: datetime):
        try:
            new_sub = Subscriptions(tenant_id=subscription.tenant_id, installation_uuid=subscription.installation_uuid, plan_id=subscription.plan_id, subscription_type=subscription.subscription_type, state="trial", trial_ends_at=trial_ends_at)
            self.db.add(new_sub)
            await self.db.commit()
            await self.db.refresh(new_sub)
            return new_sub
        except Exception as error:
            raise error

    async def get_by_id(self, subscription_id: uuid.UUID):
        try:
            result = await self.db.execute(select(Subscriptions).where(Subscriptions.id == subscription_id))
            return result.scalars().one_or_none()
        except Exception as error:
            raise error

    async def get_by_installation_uuid(self, installation_uuid: uuid.UUID):
        try:
            result = await self.db.execute(select(Subscriptions).where(Subscriptions.installation_uuid == installation_uuid))
            return result.scalars().one_or_none()
        except Exception as error:
            raise error

    async def update_state(self, subscription: Subscriptions, new_state: str, **kwargs):
        try:
            subscription.state = new_state
            for field, value in kwargs.items():
                setattr(subscription, field, value)
            await self.db.commit()
            await self.db.refresh(subscription)
            return subscription
        except Exception as error:
            raise error

    async def log_usage(self, subscription_id: uuid.UUID, installation_uuid: uuid.UUID, payload: dict):
        try:
            log = UsageLog(subscription_id=subscription_id, installation_uuid=installation_uuid, payload=payload)
            self.db.add(log)
            await self.db.commit()
        except Exception as error:
            raise error
