from ..repository.tenants import TenantsRepository
from ..schemas.tenants import TenantsCreate, TenantsResponse

class TenantsService:
    def __init__(self, repo:TenantsRepository):
        self.repo=repo
    
    async def create_tenant(self, tenant:TenantsCreate):
        try:
            new_tenant_instance = await self.repo.create_tenant(tenant=tenant)
            return new_tenant_instance
        except Exception as error:
            raise error
    
    async def get_all_tenants(self):
        try:
            tenants = await self.repo.get_all_tenants()
            return tenants
        except Exception as error:
            raise error
