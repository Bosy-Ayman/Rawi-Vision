from celery import Celery
import asyncio
from utils.celery_client import celery_app

# Queue routing - dedicated queue for face recognition (uses cached models)
celery_app.conf.task_routes = {
    "camera_ingestion.celery_tasks.face_recognition.tasks.run_face_recognition_logic": {"queue": "face_recognition"},
}

@celery_app.task(queue="face_recognition", name="camera_ingestion.celery_tasks.face_recognition.tasks.run_face_recognition_logic")
def run_face_recognition_logic(db_config, rtsp_urls, camera_identifier=None, task_id=None):
    # Lazy import to prevent memory issues during backend startup
    from ...ai.fusion import run_pipeline
    print(f"[Face Recognition Task] Starting with cache optimization...")
    run_pipeline(db_config, rtsp_urls, camera_identifier=camera_identifier, task_id=task_id)

