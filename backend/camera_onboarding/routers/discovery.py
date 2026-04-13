from fastapi import APIRouter, status, HTTPException, Form, Depends
from ..service.automatic_discovery import AutomaticDiscovery, OnvifOnboarding, NonOnvifOnboarding
from ..service.metadata import CameraMetadataService
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from ..repository.cameras import CameraRepository
from ..repository.camera_metadata import CameraMetadataRepository
from ..schemas.metadata import CameraMetadataResponse
from typing import List

camera_discovery_router = APIRouter(prefix="/camera_discovery", tags=["discover online cameras"])

async def get_camera_repository(db: AsyncSession=Depends(get_db)):
    return CameraRepository(db=db)

async def get_onvif_onboarding():
    return OnvifOnboarding()

async def get_non_onvif_onboarding():
    return NonOnvifOnboarding()

async def get_metadata_repository(db: AsyncSession=Depends(get_db)):
    return CameraMetadataRepository(db=db)

async def get_metadata_service(repo: CameraMetadataRepository=Depends(get_metadata_repository)):
    return CameraMetadataService(repository=repo)

async def get_automatic_discovery(onvif_onboarding: OnvifOnboarding=Depends(get_onvif_onboarding), non_onvif_onboarding: NonOnvifOnboarding=Depends(get_non_onvif_onboarding), repo:CameraRepository = Depends(get_camera_repository), metadata_service = Depends(get_metadata_service)):
    return AutomaticDiscovery(repo=repo, onvif_onboarding=onvif_onboarding, non_onvif_onboarding=non_onvif_onboarding, metadata_service=metadata_service)

@camera_discovery_router.get("/discovery", response_model=List[CameraMetadataResponse], status_code=status.HTTP_200_OK, description="automatic discovery of online cameras")
async def discover_online_cameras(automatic_discovery: AutomaticDiscovery = Depends(get_automatic_discovery)):
    camera_metadata = await automatic_discovery.sync_camera_metadata()
    return camera_metadata

# the below two routers are for debugging purposes only, pleaaase do not uncomment

# @camera_discovery_router.get("", response_model=list[CameraMetadataResponse])
# async def get_all_camera_metadata(service: CameraMetadataService=Depends(get_metadata_service)):
#     try:
#         camera_metadata= await service.get_all_camera_metadata()
#         return camera_metadata
#     except Exception as error:
#         raise HTTPException(status_code=status.HTTP_200_OK)

# @camera_discovery_router.delete("/{ip}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_camera(ip:str , service: CameraMetadataService = Depends(get_metadata_service)):
#     try:
#         await service.delete_camera_metadata_by_ip(ip)
#     except Exception as error:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="camera not found")