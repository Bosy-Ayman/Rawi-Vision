from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.plans import PlansCreate, PlansResponse
from ..models.plans import Plans
from sqlalchemy import select

class PlansRepository:
    def __init__(self, db:AsyncSession):
        self.db = db
    
    async def create_plan(self, plan: PlansCreate):
        try:
            new_plan_instance = Plans(name=plan.name, description= plan.description, annual_pricing=plan.annual_pricing, monthly_pricing=plan.monthly_pricing, tier= plan.tier)
            self.db.add(new_plan_instance)
            await self.db.commit()       
            await self.db.refresh(new_plan_instance)
            return new_plan_instance
        except Exception as error:
            raise error
    
    async def get_all_plans(self):
        try:
            result = await self.db.execute(select(Plans))
            plans_instances = result.scalars().all()
            return plans_instances
        except Exception as error:
            raise error

    async def get_plan_by_name(self, name):
        try:
            result = await self.db.execute(select(Plans).where(Plans.name == name))
            plan = result.scalars().one_or_none()
            return plan
        except Exception as error:
            raise error

    async def delete_plan(self, name):
        try:
            plan = await self.get_plan_by_name(name=name)
            await self.db.delete(plan)
            await self.db.commit() 
        except Exception as error:
            raise error