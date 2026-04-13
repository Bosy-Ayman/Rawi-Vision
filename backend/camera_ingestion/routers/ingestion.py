from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from camera_onboarding.repository.cameras import CameraRepository
from camera_onboarding.repository.camera_metadata import CameraMetadataRepository
from camera_onboarding.service.metadata import CameraMetadataService
from camera_onboarding.service.onvif_onboarding import OnvifOnboarding
from camera_onboarding.service.non_onvif_onboarding import NonOnvifOnboarding
from camera_onboarding.service.automatic_discovery import AutomaticDiscovery 
from ..service.ingestion import IngestionService

ingestion_router = APIRouter(prefix="/ingestion", tags=["ingestion"])

async def get_ingestion_service(db: AsyncSession = Depends(get_db)) -> IngestionService:
    meta_service = CameraMetadataService(CameraMetadataRepository(db))
    disc_service = AutomaticDiscovery(OnvifOnboarding(), NonOnvifOnboarding(), CameraRepository(db), meta_service)
    return IngestionService(meta_service, disc_service)

@ingestion_router.get("/start")
async def start_ingestion(service: IngestionService = Depends(get_ingestion_service)):
    try:
        return await service.start_ingestion()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))