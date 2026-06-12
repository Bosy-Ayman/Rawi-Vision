from camera_onboarding.service.metadata import CameraMetadataService
from camera_onboarding.service.automatic_discovery import AutomaticDiscovery
from ..celery_tasks.ingestion.tasks import capture_rtsp_video
import redis
import json
from uuid import uuid4
from ..utils.redis import redis_client
from ..celery_tasks.face_recognition.tasks import run_face_recognition_logic
from config import Config

class IngestionService:
    def __init__(self, metadata_service: CameraMetadataService, discovery_service: AutomaticDiscovery):
        self.metadata_service = metadata_service
        self.discovery_service = discovery_service
        self.db_config = Config.DB_CONFIG
    
    async def get_online_cameras(self):
        # We only look at the database. NEVER do a network scan here as it freezes the backend.
        cameras = await self.metadata_service.get_all_camera_metadata()
        return cameras if cameras else []

    async def start_ingestion(self, duration=120):
        redis_client.delete("stop_all_cameras")
        task_ids=[]
        cameras = await self.get_online_cameras()
        
        if not cameras:
            print("[IngestionService] Warning: No cameras found in database. Nothing to start.")
            return

        print(f"[IngestionService] Starting ingestion for {len(cameras)} cameras...")
        
        for camera in cameras:
            rtsp_urls = camera.rtsp_urls
            task_id = str(uuid4())
            
            # Start Face Recognition
            camera_identifier = camera.ip_address or camera.mac_address
            run_face_recognition_logic.delay(self.db_config, rtsp_urls, camera_identifier=camera_identifier, task_id=task_id)
            
            # Video recording is currently commented out to save system resources
            # capture_rtsp_video.delay(rtsp_urls, camera.mac_address, task_id, duration=30)
            
            task_ids.append(task_id) 
            
        redis_client.set('task_ids', json.dumps(task_ids))

    def stop_ingestion(self):
        redis_client.set("stop_all_cameras", 1)
        task_ids_json = redis_client.get("task_ids")
        if task_ids_json is None:
            return
        try:
            task_ids = json.loads(task_ids_json)
        except json.JSONDecodeError:
            print("Invalid JSON in Redis:", task_ids_json)
            return
        for task_id in task_ids:
            redis_client.set(f"stop:{task_id}", 1)
