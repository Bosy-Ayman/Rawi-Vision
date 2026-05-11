from ..repository.subscriptions import SubscriptionsRepository
from ..repository.plans import PlansRepository
from ..schemas.subscriptions import SubscriptionCreate, CheckInRequest
from ..schemas.license import LicenseTokenPayload
from ..services.license import LicenseService
from ..utils.exceptions import SubscriptionNotFound, InvalidStateTransition, PlanNotFound
from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone
import uuid

class SubscriptionsService:
    def __init__(self, subscription_repo: SubscriptionsRepository, plans_repo: PlansRepository):
        self.subscription_repo = subscription_repo
        self.plans_repo = plans_repo
        self.license_service = LicenseService()
        self.VALID_TRANSITIONS = {
            "trial":    {"active", "canceled"},
            "active":   {"past_due", "canceled"},
            "past_due": {"active", "canceled", "expired"},
            "canceled": set(),
            "expired":  set(),
        }
        self.TERMINAL_STATES = {"canceled", "expired"}
    
    # helper functions
    def _calculate_trial_end(self, subscription_type: str):
        now = datetime.now(timezone.utc)
        if subscription_type == "monthly":
            return now + relativedelta(months=1)
        elif subscription_type == "annual":
            return now + relativedelta(years=1)
        raise ValueError("Invalid subscription_type. Use 'monthly' or 'annual'.")

    def _get_entitlements(self, plan_name: str):
        defaults = {"plan": plan_name}
        return defaults

    def _mint(self, sub):
        payload = LicenseTokenPayload(installation_uuid=sub.installation_uuid, tenant_id=sub.tenant_id, plan_id=sub.plan_id, subscription_state=sub.state, subscription_type=sub.subscription_type, entitlements=self._get_entitlements(sub.plan_id))
        return self.license_service.mint_token(payload)

    async def _get_or_raise(self, subscription_id: uuid.UUID):
        sub = await self.subscription_repo.get_by_id(subscription_id)
        if not sub:
            raise SubscriptionNotFound(f"Subscription {subscription_id} not found")
        return sub

    def _assert_transition(self, current_state: str, target_state: str):
        if target_state not in self.VALID_TRANSITIONS.get(current_state, set()):
            raise InvalidStateTransition(f"Cannot transition from '{current_state}' to '{target_state}'")

    async def create_subscription(self, subscription: SubscriptionCreate):
        try:
            plan = await self.plans_repo.get_plan_by_name(subscription.plan_id)
            if not plan:
                raise PlanNotFound(f"Plan '{subscription.plan_id}' not found")
            trial_ends_at = self._calculate_trial_end(subscription.subscription_type)
            sub = await self.subscription_repo.create_subscription(subscription=subscription, trial_ends_at=trial_ends_at)
            token = self._mint(sub)
            return sub, token
        except Exception as error:
            raise error

    
    # life cycle transitions
    async def activate(self, subscription_id: uuid.UUID):
        try:
            sub = await self._get_or_raise(subscription_id)
            self._assert_transition(sub.state, "active")
            now = datetime.now(timezone.utc)
            if sub.subscription_type == "monthly":
                cycle_end = now + relativedelta(months=1)
            else:
                cycle_end = now + relativedelta(years=1)
            sub = await self.subscription_repo.update_state(sub, "active", billing_cycle_start=now, billing_cycle_end=cycle_end)
            token = self._mint(sub)
            return sub, token
        except Exception as error:
            raise error

    async def mark_past_due(self, subscription_id: uuid.UUID):
        try:
            sub = await self._get_or_raise(subscription_id)
            self._assert_transition(sub.state, "past_due")
            sub = await self.subscription_repo.update_state(sub, "past_due")
            token = self._mint(sub)
            return sub, token
        except Exception as error:
            raise error

    async def cancel(self, subscription_id: uuid.UUID):
        try:
            sub = await self._get_or_raise(subscription_id)
            self._assert_transition(sub.state, "canceled")
            sub = await self.subscription_repo.update_state(sub, "canceled", canceled_at=datetime.now(timezone.utc))
            return sub
        except Exception as error:
            raise error

    async def expire(self, subscription_id: uuid.UUID):
        try:
            sub = await self._get_or_raise(subscription_id)
            self._assert_transition(sub.state, "expired")
            sub = await self.subscription_repo.update_state(sub, "expired")
            return sub
        except Exception as error:
            raise error

    async def change_plan(self, subscription_id: uuid.UUID, new_plan_id: str):
        try:
            sub = await self._get_or_raise(subscription_id)
            if sub.state in self.TERMINAL_STATES:
                raise InvalidStateTransition("Cannot change plan on a terminal subscription")
            plan = await self.plans_repo.get_plan_by_name(new_plan_id)
            if not plan:
                raise PlanNotFound(f"Plan '{new_plan_id}' not found")
            sub = await self.subscription_repo.update_state(sub, sub.state, plan_id=new_plan_id)
            token = self._mint(sub)
            return sub, token
        except Exception as error:
            raise error


    async def check_in(self, request: CheckInRequest):
        try:
            # 1. Validate the incoming token
            try:
                claims = self.license_service.decode_token(request.token)
            except Exception:
                return {"status": "suspended", "token": None, "message": "Invalid or expired token"}

            # 2. Make sure installation_uuid in token matches the request
            if str(request.installation_uuid) != claims.get("installation_uuid"):
                return {"status": "suspended", "token": None, "message": "Installation UUID mismatch"}

            # 3. Look up the live subscription record
            sub = await self.subscription_repo.get_by_installation_uuid(request.installation_uuid)
            if not sub:
                return {"status": "suspended", "token": None, "message": "No subscription found for this installation"}

            # 4. Ingest usage data
            await self.subscription_repo.log_usage(subscription_id=sub.id, installation_uuid=request.installation_uuid, payload=request.usage)

            # 5. Return signal based on live state
            if sub.state in ("canceled", "expired"):
                return {"status": sub.state, "token": None, "message": f"Subscription {sub.state}"}

            if sub.state == "past_due":
                return {"status": "suspended", "token": None, "message": "Payment overdue"}

            # 6. Issue a fresh token
            fresh_token = self._mint(sub)
            return {"status": "ok", "token": fresh_token, "message": None}

        except Exception as error:
            raise error
