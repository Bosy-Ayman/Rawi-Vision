from fastapi import Depends, APIRouter, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from ..service.stream import StreamService
from camera_onboarding.service.metadata import CameraMetadataService
from camera_onboarding.repository.camera_metdata import CameraMetadataRepository
from fastapi import WebSocket
from auth.dependencies import require_manager_ws

stream_router = APIRouter(prefix="/stream", tags=["gets live stream from online cameras"])

async def get_metadata_repository(db: AsyncSession=Depends(get_db)):
    return CameraMetadataRepository(db=db)

async def get_metadata_service(repo: CameraMetadataRepository=Depends(get_metadata_repository)):
    return CameraMetadataService(repository=repo)

async def get_stream_service(metadata_service: CameraMetadataService=Depends(get_metadata_service)):
    return StreamService(camera_metadata_service=metadata_service)

@stream_router.websocket("/{camera_ip}")
async def start_stream(
    websocket: WebSocket,
    camera_ip: str,
    token_payload: dict = Depends(require_manager_ws),
    service: StreamService = Depends(get_stream_service)
):
    await service.stream(websocket=websocket, camera_ip=camera_ip)