from .non_onvif_onboarding import NonOnvifOnboarding
from .onvif_onboarding import OnvifOnboarding
from ..repository.cameras import CameraRepository
from ..schemas.metadata import CameraMetadataResponse, CameraMetadataCreate
import asyncio
from .metadata import CameraMetadataService
import cv2

class AutomaticDiscovery():
    def __init__(self, onvif_onboarding: OnvifOnboarding, non_onvif_onboarding: NonOnvifOnboarding, repo: CameraRepository, metadata_service: CameraMetadataService):
        self.onvif_onboarding = onvif_onboarding
        self.non_onvif_onboarding = non_onvif_onboarding
        self.repo = repo
        self.metadata_service = metadata_service

    async def discover_camera_ips(self):
        camera_ips = [] 
        onvif_ips = self.onvif_onboarding.get_camera_ip_addresses() # this could be slowing down my code
        db_cameras = await self.repo.get_all_cameras()
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, lambda c=camera: self.non_onvif_onboarding.get_camera_ip_addresses(username=c.username, password=c.password)) for camera in db_cameras]
        results = await asyncio.gather(*tasks) 
        for non_onvif_ips in results:
            camera_ips.extend(non_onvif_ips)
        camera_ips.extend(onvif_ips)
        return camera_ips
    
    def check_path(self, username, password, ip, path):
        url = f"rtsp://{username}:{password}@{ip}:554{path}"
        cap = cv2.VideoCapture()
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        cap.open(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            print(f"Failed to connect (IP may be down): {url}")
            return False
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None or frame.size == 0:
            print(f"Stream unreachable or returned empty frame: {url}")
            return False
        return True

    async def check_saved_camera_metadata_validity(self, ip):
        camera_metadata = await self.metadata_service.get_camera_metadata_by_ip(ip=ip)
        if self.check_path(username=camera_metadata.username, password=camera_metadata.password, ip=camera_metadata.ip_address, path=camera_metadata.rtsp_urls[0]):
            return True
        return False
    
    async def discover_mac_address_and_rtsp_url(self, ip_address):
        mac_address = self.onvif_onboarding.discover_mac_address(ip=ip_address)
        if not mac_address:
            return [None, None]
        cameras = await self.repo.get_all_cameras()
        for camera in cameras:
            if camera.mac_address == mac_address:
                result_camera = camera
                rtsp_urls = self.onvif_onboarding.get_rtsp_url(ip=ip_address, username=result_camera.username, password=result_camera.password)
                return [mac_address, rtsp_urls]
        return [mac_address, None]

    async def sync_camera_metadata(self):
        camera_ips = await self.discover_camera_ips()
        print(camera_ips)
        cameras_metadata = await self.metadata_service.get_all_camera_metadata()
        saved_camera_metadata_ips = {camera.ip_address: camera for camera in cameras_metadata} 
        for ip, camera in saved_camera_metadata_ips.items():
            if not await self.check_saved_camera_metadata_validity(ip=camera.ip_address):
                await self.metadata_service.delete_camera_metadata_by_ip(ip_address=camera.ip_address)
        for ip in camera_ips:
            if ip in saved_camera_metadata_ips:
                if await self.check_saved_camera_metadata_validity(ip=ip):
                    continue
                else:
                    await self.metadata_service.delete_camera_metadata_by_ip(ip_address=ip) 
                    continue
            [mac_address, rtsp_urls] = await self.discover_mac_address_and_rtsp_url(ip_address=ip)
            if mac_address is None or rtsp_urls is None:  
                continue
            existing = await self.metadata_service.get_camera_metadata_by_mac_address(mac_address=mac_address)
            if existing:
                continue
            camera_metadata = await self.repo.get_camera_by_mac_address(mac_address=mac_address)
            camera_metadata_instance = CameraMetadataCreate(mac_address=mac_address, ip_address=ip, rtsp_urls=rtsp_urls, username=camera_metadata.username, password=camera_metadata.password, room=camera_metadata.room, building=camera_metadata.building,)
            await self.metadata_service.create_camera_metadata_instance(camera_metadata_instance)
        return await self.metadata_service.get_all_camera_metadata()

    
    