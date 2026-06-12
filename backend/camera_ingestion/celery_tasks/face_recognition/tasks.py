from celery import Celery
import asyncio
from utils.celery_client import celery_app

@celery_app.task
def run_face_recognition_logic(db_config, rtsp_urls, camera_identifier=None, task_id=None):
    # Lazy import to prevent memory issues during backend startup
    from ...ai.fusion import run_pipeline
    run_pipeline(db_config, rtsp_urls, camera_identifier=camera_identifier, task_id=task_id)
