from fastapi import Depends, APIRouter, status, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from ..service.ingestion import IngestionService
from camera_onboarding.service.metadata import CameraMetadataService
from camera_onboarding.repository.camera_metdata import CameraMetadataRepository
from ..service.stream import StreamService
from camera_onboarding.service.automatic_discovery import AutomaticDiscovery
from camera_onboarding.service.onvif_onboarding import OnvifOnboarding
from camera_onboarding.service.non_onvif_onboarding import NonOnvifOnboarding
from camera_onboarding.repository.cameras import CameraRepository

ingestion_router = APIRouter(prefix="/ingestion", tags=["manage online cameras ingestion"])

async def get_metadata_repository(db: AsyncSession=Depends(get_db)):
    return CameraMetadataRepository(db=db)

async def get_metadata_service(repo: CameraMetadataRepository=Depends(get_metadata_repository)):
    return CameraMetadataService(repository=repo)

async def get_onvif_onboarding():
    return OnvifOnboarding()

async def get_non_onvif_onboarding():
    return NonOnvifOnboarding()

async def get_camera_repository(db: AsyncSession=Depends(get_db)):
    return CameraRepository(db=db)

async def get_automatic_discovery_service(onvif_onboarding: OnvifOnboarding=Depends(get_onvif_onboarding), non_onvif_onboarding:NonOnvifOnboarding=Depends(get_non_onvif_onboarding), camera_repo:CameraRepository=Depends(get_camera_repository), camera_metadata_service:CameraMetadataService=Depends(get_metadata_service)):
    return AutomaticDiscovery(onvif_onboarding=onvif_onboarding, non_onvif_onboarding=non_onvif_onboarding, repo=camera_repo, metadata_service=camera_metadata_service)

async def get_ingestion_service(metadata_service: CameraMetadataService=Depends(get_metadata_service), discovery_service:AutomaticDiscovery=Depends(get_automatic_discovery_service)):
    return IngestionService(metadata_service=metadata_service, discovery_service=discovery_service)

async def get_stream_service(metadata_service: CameraMetadataService=Depends(get_metadata_service)):
    return StreamService(camera_metadata_service=metadata_service)

@ingestion_router.get("/start", status_code=status.HTTP_200_OK)
async def start_ingestion(service: IngestionService = Depends(get_ingestion_service)):
    try: 
        await service.start_ingestion()
        return {"status":"started"}
    except Exception as error: 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{error}")

@ingestion_router.get("/stop", status_code=status.HTTP_200_OK)
def stop_ingestion(service: IngestionService = Depends(get_ingestion_service)):
    try: 
        service.stop_ingestion()
        return {"status":"stopped"}
    except Exception as error: 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{error}")



