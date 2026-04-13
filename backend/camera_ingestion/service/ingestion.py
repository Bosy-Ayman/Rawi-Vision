from camera_onboarding.service.metadata import CameraMetadataService
from camera_onboarding.service.automatic_discovery import AutomaticDiscovery 
from ..celery_tasks.ingestion import capture_rtsp_video
from ..celery_tasks.face_recognition import run_face_recognition_logic
from ..utils.redis import redis_client
import json
from uuid import uuid4

class IngestionService:
    def __init__(self, metadata_service: CameraMetadataService, discovery_service: AutomaticDiscovery):
        self.metadata_service = metadata_service
        self.discovery_service = discovery_service
        self.db_config = {
            "host": "localhost",
            "port": 5432,
            "dbname": "rawivision_db",
            "user": "shahd",
            "password": "password"
        }
    
    async def get_online_cameras(self):
        cameras = await self.metadata_service.get_all_camera_metadata() 
        if not cameras:
            print("Metadata DB is empty. Running network discovery...")
            cameras = await self.discovery_service.sync_camera_metadata()
        return cameras

    async def start_ingestion(self, duration=120):
        task_ids = []
        cameras = await self.get_online_cameras()
        
        if not cameras:
            raise RuntimeError("No online cameras found on network or DB")
            
        for camera in cameras:
            rtsp_urls = camera.rtsp_urls
            task_id = str(uuid4())
            capture_rtsp_video.delay(rtsp_urls, camera.mac_address, task_id, duration=30)
            run_face_recognition_logic.delay(self.db_config, rtsp_urls)
            task_ids.append(task_id) 
            
        redis_client.set('task_ids', json.dumps(task_ids))
        return {"status": "started", "tasks": task_ids}

    def stop_ingestion(self):
        task_ids_json = redis_client.get("task_ids")
        if task_ids_json is None: return
        try:
            task_ids = json.loads(task_ids_json)
        except json.JSONDecodeError:
            print("Invalid JSON in Redis:", task_ids_json)
            return
            
        for task_id in task_ids:
            redis_client.set(f"stop:{task_id}", 1)