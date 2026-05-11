from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.tenants import TenantsCreate
from ..models.tenants import Tenants
from sqlalchemy import select


class TenantsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, tenant: TenantsCreate):
        try:
            new_tenant_instance = Tenants(
                installation_uuid=tenant.installation_uuid,   
                name=tenant.name,
                phone_no=tenant.phone_no,
                contact_email=tenant.contact_email,
                access_email=tenant.access_email,
                access_password=tenant.access_password,
            )
            self.db.add(new_tenant_instance)
            await self.db.commit()
            await self.db.refresh(new_tenant_instance)
            return new_tenant_instance
        except Exception as error:
            raise error

    async def get_all_tenants(self):
        try:
            result = await self.db.execute(select(Tenants))
            return result.scalars().all()
        except Exception as error:
            raise error
