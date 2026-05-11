from fastapi import APIRouter, status, HTTPException, Depends
from ..schemas.license_store import TokenRegisterRequest, LicenseStoreResponse, EntitlementsResponse, CheckInLogResponse
from ..repository.license_store import LicenseStoreRepository
from ..services.license_store import LicenseStoreService
from ..utils.exceptions import LicenseNotFound, LicenseInvalid
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

license_router = APIRouter(prefix="/license", tags=["license"])

async def get_license_repo(db: AsyncSession = Depends(get_db)):
    return LicenseStoreRepository(db=db)

async def get_license_service(repo: LicenseStoreRepository = Depends(get_license_repo)):
    return LicenseStoreService(repo=repo)

#should be called once, after the first tenants boot
@license_router.post("/register", response_model=LicenseStoreResponse, status_code=status.HTTP_200_OK)
async def register_token(body: TokenRegisterRequest, service: LicenseStoreService = Depends(get_license_service)):
    try:
        store = await service.register_token(body.installation_uuid, body.token)
        return store
    except LicenseInvalid as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@license_router.get("/{installation_uuid}/validate", response_model=EntitlementsResponse, status_code=status.HTTP_200_OK)
async def validate_license(installation_uuid: UUID, service: LicenseStoreService = Depends(get_license_service)):
    try:
        result = await service.validate(installation_uuid)
        return EntitlementsResponse(**result)
    except LicenseNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except LicenseInvalid as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@license_router.post("/{installation_uuid}/check-in", status_code=status.HTTP_200_OK)
async def check_in(installation_uuid: UUID, usage: dict, service: LicenseStoreService = Depends(get_license_service)):
    try:
        result = await service.perform_check_in(installation_uuid, usage)
        return result
    except LicenseNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@license_router.get("/{installation_uuid}/check-in/logs", response_model=list[CheckInLogResponse], status_code=status.HTTP_200_OK)
async def get_check_in_logs(installation_uuid: UUID, service: LicenseStoreService = Depends(get_license_service)):
    try:
        logs = await service.repo.get_check_in_logs(installation_uuid)
        return logs
    except Exception as error:
        raise error
