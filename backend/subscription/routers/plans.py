from fastapi import APIRouter, status, HTTPException, Depends, Form
from ..schemas.plans import PlansCreate, PlansUpdate, PlansResponse
from ..repository.plans import PlansRepository
from ..services.plans import PlansService
from database import db_dependency, get_db
from sqlalchemy.ext.asyncio import AsyncSession

plan_router = APIRouter(prefix="/plans", tags=["CRUD for subscription plans"])

async def get_plan_repository(db: AsyncSession = Depends(get_db)):
    return PlansRepository(db=db)

async def get_plans_service(repo: PlansRepository = Depends(get_plan_repository)):
    return PlansService(repo=repo)

@plan_router.get("", response_model=list[PlansResponse], status_code=status.HTTP_200_OK)
async def get_all_plans(service: PlansService = Depends(get_plans_service)):
    try:
        plans = await service.get_all_plans()
        return plans
    except Exception as error:
        raise EOFError

@plan_router.post("", response_model=PlansResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(name:str = Form(...), description:str = Form(...), tier:str=Form(...), annual_pricing: int=Form(...), monthly_pricing:int = Form(...), service: PlansService = Depends(get_plans_service)):
    try:
        plan = PlansCreate(name=name, tier=tier, description=description, monthly_pricing=monthly_pricing, annual_pricing=annual_pricing)
        created_plan = await service.create_new_plan(plan=plan)
        return created_plan
    except Exception as error:
        raise error

@plan_router.patch("", response_model=PlansResponse, status_code=status.HTTP_200_OK)
async def update_plan_partially(name: str, plan_new_data: PlansUpdate, service:PlansService=Depends(get_plans_service)):
    try:
        new_plan=await service.update_plan(name=name, updated_plan=plan_new_data)
        return new_plan
    except Exception as error:
        raise error

@plan_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(name:str, service:PlansService = Depends(get_plans_service)):
    try:
        await service.delete_plan(name=name)
    except Exception as error:
        raise error
    