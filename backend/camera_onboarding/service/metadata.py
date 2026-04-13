from ..repository.camera_metadata import CameraMetadataRepository
from ..schemas.metadata import CameraMetadataCreate, CameraMetadataResponse
from ..utils.exceptions import CameraNotFound

class CameraMetadataService:
    def __init__(self, repository: CameraMetadataRepository):
        self.repository = repository
    
    async def create_camera_metadata_instance(self, camera_metadata: CameraMetadataCreate):
        try:
            new_camera_metadata_instance = await self.repository.create_camera_metadata_instance(camera=camera_metadata)
            await self.repository.db.commit()
            await self.repository.db.refresh(new_camera_metadata_instance)
            return new_camera_metadata_instance
        except Exception as error:
            await self.repository.db.rollback()
            raise error

    async def get_camera_metadata_by_ip(self, ip:str):
        try:
            camera_metadata = await self.repository.get_camera_metadata_by_ip(ip=ip)
            return camera_metadata
        except Exception as error:
            raise error
    
    async def get_camera_metadata_by_mac_address(self, mac_address:str):
        try:
            camera_metadata = await self.repository.get_camera_metadata_by_mac_address(mac_address=mac_address)
            return camera_metadata
        except Exception as error:
            raise error

    async def get_all_camera_metadata(self):
        try:
            cameras = await self.repository.get_all_camera_metadata()
            return cameras
        except Exception as error:
            raise error
    
    async def delete_camera_metadata_by_ip(self, ip_address: str):
        try:
            camera = await self.repository.get_camera_metadata_by_ip(ip=ip_address)
            if not camera:
                raise CameraNotFound
            await self.repository.delete_camera(camera=camera)
            await self.repository.db.commit()
        except Exception as error:
            await self.repository.db.rollback()
            raise error
    
