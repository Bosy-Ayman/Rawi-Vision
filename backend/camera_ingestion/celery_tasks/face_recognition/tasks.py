from ...ai.fusion import run_pipeline
from celery import Celery
import asyncio
from utils.celery_client import celery_app

@celery_app.task
def run_face_recognition_logic(db_config, rtsp_urls):
    asyncio.run(run_pipeline(db_config, rtsp_urls))
