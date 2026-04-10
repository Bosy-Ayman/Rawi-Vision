from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.metadata import CameraMetadataCreate, CameraMetadataResponse
from ..models.camera_metadata import CameraMetadata
from sqlalchemy import select

class CameraMetadataRepository:
    def __init__(self, db:AsyncSession):
        self.db = db
    
    async def create_camera_metadata_instance(self, camera:CameraMetadataCreate):
        try:
            new_metadata_instance = CameraMetadata(room=camera.room, building=camera.building ,mac_address= camera.mac_address, ip_address=camera.ip_address, rtsp_urls= camera.rtsp_urls, username=camera.username, password= camera.password)
            self.db.add(new_metadata_instance)
            await self.db.flush()
            return new_metadata_instance
        except Exception as error:
            raise error
    
    async def get_all_camera_metadata(self):
        try:
            result = await self.db.execute(select(CameraMetadata))
            metadata_instances = result.scalars().all()
            return metadata_instances
        except Exception as error:
            raise error
    
    async def get_camera_metadata_by_mac_address(self, mac_address: str):
        try:
            result = await self.db.execute(select(CameraMetadata).where(CameraMetadata.mac_address == mac_address))
            camera = result.scalars().one_or_none()
            return camera
        except Exception as error:
            raise error
    
    async def get_camera_metadata_by_ip(self, ip: str):
        try:
            result = await self.db.execute(select(CameraMetadata).where(CameraMetadata.ip_address == ip))
            camera = result.scalars().one_or_none()
            return camera
        except Exception as error:
            raise error 

    async def delete_camera(self, camera:CameraMetadata):
        try:
            await self.db.delete(camera)
        except Exception as error:
            raise error