from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.camera import CameraCreate, CameraResponse
from ..models.camera import Camera
from uuid import UUID
from sqlalchemy import select

class CameraRepository:
    def __init__(self, db:AsyncSession):
        self.db = db
    
    async def create_camera_instance(self, camera:CameraCreate):
        try:
            new_camera_instance = Camera(room = camera.room, building = camera.building, mac_address = camera.mac_address, username= camera.username, password= camera.password)
            self.db.add(new_camera_instance)
            await self.db.flush()
            return new_camera_instance
        except Exception as error:
            raise error
    
    async def get_all_cameras(self):
        try:
            result = await self.db.execute(select(Camera))
            camera_instances = result.scalars().all()
            return camera_instances
        except Exception as error:
            raise error
    
    async def get_camera_by_id(self, id: UUID):
        try:
            result = await self.db.execute(select(Camera).where(Camera.id == id))
            camera = result.scalars().one_or_none()
            return camera
        except Exception as error:
            raise error
    
    async def get_camera_by_mac_address(self, mac_address:str):
        try:
            result = await self.db.execute(select(Camera).where(Camera.mac_address == mac_address))
            camera = result.scalars().one_or_none()
            return camera
        except Exception as error:
            raise error
    
    async def delete_camera(self, camera:Camera):
        try:
            await self.db.delete(camera)
        except Exception as error:
            raise error