from camera_onboarding.service.metadata import CameraMetadataService
from ..celery_tasks.ingestion.tasks import capture_rtsp_video
import redis
import json
from uuid import uuid4
from ..utils.redis import redis_client
from ..celery_tasks.face_recognition.tasks import run_face_recognition_logic
from config import Config

class IngestionService:
    def __init__(self, service: CameraMetadataService):
        self.service = service
        self.db_config =  Config.DB_CONFIG
    
    async def get_online_cameras(self):
        cameras = await self.service.get_all_camera_metadata() # calling this instead of the sync function beacuse this one takes less time for running
        return cameras

    async def start_ingestion(self, duration=120):
        task_ids=[]
        cameras = await self.get_online_cameras()
        if not cameras:
            raise RuntimeError("No online cameras")
        for camera in cameras:
            rtsp_urls = camera.rtsp_urls
            task_id = str(uuid4())
            capture_rtsp_video.delay(rtsp_urls, camera.mac_address, task_id, duration=30)
            run_face_recognition_logic.delay(self.db_config, rtsp_urls)
            task_ids.append(task_id) 
        redis_client.set('task_ids', json.dumps(task_ids))

    def stop_ingestion(self):
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
    




