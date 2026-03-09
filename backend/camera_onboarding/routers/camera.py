from fastapi import APIRouter, status, HTTPException, Form, Depends
from ..service.camera import CameraService
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from ..repository.cameras import CameraRepository
from ..schemas.camera import CameraResponse, CameraCreate
from uuid import UUID

camera_router = APIRouter(prefix="/camera", tags=["cameras"])

async def get_camera_repository(db: AsyncSession=Depends(get_db)):
    return CameraRepository(db=db)

async def get_camera_service(repo: CameraRepository = Depends(get_camera_repository)):
    return CameraService(repository=repo)

@camera_router.get("", response_model=list[CameraResponse])
async def get_all_cameras(service: CameraService = Depends(get_camera_service)):
    try:
        cameras = await service.get_all_cameras()
        return cameras
    except Exception as error:
        raise error

@camera_router.post("", response_model=CameraResponse, status_code= status.HTTP_201_CREATED)
async def create_camera(room: str = Form(...), building: str = Form(...), mac_address: str = Form(...), service: CameraService = Depends(get_camera_service)):
    try:
        camera = CameraCreate(room=room, building=building, mac_address=mac_address)
        created_camera = await service.create_camera_instance(camera=camera)
        return created_camera
    except Exception as error:
        raise error

@camera_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(id: UUID, service: CameraService = Depends(get_camera_service)):
    try:
        await service.delete_camera(id=id)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="camera not found")