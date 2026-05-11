from fastapi import APIRouter, status, HTTPException, Depends, Form
from ..schemas.tenants import TenantsCreate, TenantsResponse
from ..repository.tenants import TenantsRepository
from ..services.tenants import TenantsService
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

tenant_router = APIRouter(prefix='/tenants', tags=['tenants'])


async def get_tenant_repo(db: AsyncSession = Depends(get_db)):
    return TenantsRepository(db=db)

async def get_tenant_service(repo: TenantsRepository = Depends(get_tenant_repo)):
    return TenantsService(repo=repo)


@tenant_router.post("", response_model=TenantsResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(name: str = Form(...), phone_no: str = Form(...), contact_email: str = Form(...), access_email: str = Form(...), access_password: str = Form(...), installation_uuid: UUID = Form(...), service: TenantsService = Depends(get_tenant_service)):
    try:
        new_tenant = TenantsCreate(name=name, phone_no=phone_no, contact_email=contact_email, access_email=access_email, access_password=access_password, installation_uuid=installation_uuid)
        tenant = await service.create_tenant(new_tenant)
        return tenant
    except Exception as error:
        raise error


@tenant_router.get("", response_model=list[TenantsResponse], status_code=status.HTTP_200_OK)
async def get_all_tenants(service: TenantsService = Depends(get_tenant_service)):
    try:
        tenants = await service.get_all_tenants()
        return tenants
    except Exception as error:
        raise error
