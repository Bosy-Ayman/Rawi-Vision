from ..repository.plans import PlansRepository
from ..schemas.plans import PlansCreate, PlansResponse, PlansUpdate
from ..utils.exceptions import PlanNotFound

class PlansService:
    def __init__(self, repo:PlansRepository):
        self.repo = repo
    
    async def create_new_plan(self, plan:PlansCreate):
        try:
            new_plan_instance = await self.repo.create_plan(plan=plan)
            return new_plan_instance
        except Exception as error:
            raise error
    
    async def get_all_plans(self):
        try:
            plans = await self.repo.get_all_plans()
            return plans
        except Exception as error:
            raise error
    
    async def delete_plan(self, name):
        try:
            await self.repo.delete_plan(name=name)
        except Exception as error:
            raise error
    
    async def update_plan(self, name, updated_plan: PlansUpdate):
        try:
            plan = await self.repo.get_plan_by_name(name=name)
            if not plan:
                raise PlanNotFound(f"plan with name {name} not found")
            updated_data = updated_plan.model_dump(exclude_unset=True)
            for field, value in updated_data.items():
                setattr(plan, field, value)
            await self.repo.db.commit()
            await self.repo.db.refresh(plan)
            return plan
        except Exception as error:
            raise error

