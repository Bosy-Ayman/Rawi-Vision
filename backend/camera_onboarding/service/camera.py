from ..repository.cameras import CameraRepository
from ..schemas.camera import CameraCreate, CameraResponse
from uuid import UUID
from ..utils.exceptions import CameraNotFound

class CameraService:
    def __init__(self, repository: CameraRepository):
        self.repository = repository
    
    async def create_camera_instance(self, camera: CameraCreate):
        try:
            new_camera_instance = await self.repository.create_camera_instance(camera=camera)
            await self.repository.db.commit()
            await self.repository.db.refresh(new_camera_instance)
            return new_camera_instance
        except Exception as error:
            await self.repository.db.rollback()
            raise error
    
    async def get_all_cameras(self):
        try:
            cameras = await self.repository.get_all_cameras()
            return cameras
        except Exception as error:
            raise error
    
    async def delete_camera(self, id: UUID):
        try:
            camera = await self.repository.get_camera_by_id(id=id)
            if not camera:
                raise CameraNotFound
            await self.repository.delete_camera(camera=camera)
            await self.repository.db.commit()
        except Exception as error:
            await self.repository.db.rollback()
            raise error
    
    # fadel el update camera w get camera by id
