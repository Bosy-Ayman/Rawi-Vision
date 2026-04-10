from celery import Celery
import cv2
import time
from employee_onboarding.utils.minio_client import minio_client_init
from employee_onboarding.utils.minio_storage_client import MinioStorageClient
import asyncio
import os
from ..utils.video_upload import VideoUploadFile
from celery.result import AsyncResult
from ..utils.redis import redis_client
from utils.celery_client import celery_app


minio_client_init()
minio_client = MinioStorageClient()

@celery_app.task
def capture_rtsp_video(rtsp_urls, output_path, task_id, duration=120):
    asyncio.run(_capture_rtsp_video(rtsp_urls, output_path, task_id, duration))

async def _capture_rtsp_video(rtsp_urls, output_path, task_id, duration=120):
    cap = None
    for url in rtsp_urls:
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            break
    if cap is None or not cap.isOpened():
        raise RuntimeError(f"Could not open any RTSP stream from: {rtsp_urls}")
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    safe_name = output_path.replace(":", "-")
    os.makedirs("recordings", exist_ok=True)
    try:
        while True:
            if redis_client.get(f"stop:{task_id}"):
                break
            timestamp = int(time.time())
            file_path = os.path.join("recordings", f"{safe_name}_{timestamp}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(file_path, fourcc, fps, (frame_width, frame_height))
            start_time = time.time()
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to read frame")
                    break
                out.write(frame)
                if time.time() - start_time >= duration:
                    break
            out.release()
            object_name = f"{output_path}/{timestamp}.mp4"
            await minio_client.add_object_to_bucket(upload_file=VideoUploadFile(file_path=file_path), bucket_name="cameras-ingestion", object_name=object_name)
            os.remove(file_path)  
    finally:
        cap.release()
