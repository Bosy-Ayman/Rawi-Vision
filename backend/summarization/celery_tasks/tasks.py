import os
import sys
from pathlib import Path
import tempfile
import time
import psycopg2
from datetime import datetime
from minio import Minio

# Add Summarization_Pipeline to path
backend_dir = Path(__file__).resolve().parent.parent.parent
project_dir = backend_dir.parent
summarization_pipeline_dir = project_dir / "Summarization_Pipeline"
if str(summarization_pipeline_dir) not in sys.path:
    sys.path.insert(0, str(summarization_pipeline_dir))

from utils.celery_client import celery_app
from object_detection import load_model
from motion_filter import MotionFilter
from frame_processor import save_frame
from video_generator import frames_to_video
# Import ensure_dir from Summarization_Pipeline/utils.py explicitly to avoid conflict with backend/utils
import importlib.util
spec = importlib.util.spec_from_file_location("pipeline_utils", str(summarization_pipeline_dir / "utils.py"))
pipeline_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline_utils)
ensure_dir = pipeline_utils.ensure_dir

# --- Redis helper ---
def get_redis_client():
    import redis
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )

# --- DB helper ---
def get_sync_db_conn():
    host = os.getenv("DB_HOST", "localhost")
    if host == "localhost":
        host = "127.0.0.1"
    return psycopg2.connect(
        host=host,
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "rawivision_db"),
        user=os.getenv("DB_USER", "shahd"),
        password=os.getenv("DB_PASSWORD", "password")
    )

def update_summary_status(summary_id: str, status: str, path: str = None):
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            if path:
                cur.execute(
                    "UPDATE video_summaries SET status = %s, summary_storage_path = %s, date_completed = %s WHERE id = %s",
                    (status, path, datetime.now(), summary_id)
                )
            else:
                cur.execute(
                    "UPDATE video_summaries SET status = %s WHERE id = %s",
                    (status, summary_id)
                )
        conn.commit()
    finally:
        conn.close()

# --- MinIO helper ---
def get_minio_client():
    minio_url = (
        os.getenv("MINIO_SERVER_URL", "127.0.0.1:9000")
        .replace("http://", "")
        .replace("https://", "")
    )
    return Minio(
        minio_url,
        access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        secure=False
    )

def ensure_bucket(client, bucket_name: str):
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

# Make sure this task runs on the default queue
celery_app.conf.task_routes.update({
    "summarization.tasks.generate_video_summary_task": {"queue": "celery"}
})

_GLOBAL_YOLO_MODEL = None

@celery_app.task(bind=True, name="summarization.tasks.generate_video_summary_task")
def generate_video_summary_task(self, summary_id: str, video_id: str, camera_id: str, source_storage_path: str):
    import cv2
    import shutil
    
    print(f"[TASK] Starting video summarization for summary_id={summary_id}")
    update_summary_status(summary_id, "processing")
    
    try:
        minio = get_minio_client()
        
        # Setup temporary directories for processing
        with tempfile.TemporaryDirectory() as base_output:
            selected_dir = os.path.join(base_output, camera_id, "selected_frames")
            detected_dir = os.path.join(base_output, camera_id, "detected_frames")
            summary_dir = os.path.join(base_output, camera_id, "summaries")
            
            for d in (selected_dir, detected_dir, summary_dir):
                ensure_dir(d)
                
            # Download original video
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_src:
                tmp_src_path = tmp_src.name
            
            print(f"[TASK] Downloading source video from MinIO: {source_storage_path}")
            minio.fget_object("camera-archive-videos", source_storage_path, tmp_src_path)
            
            # Setup YOLO model
            global _GLOBAL_YOLO_MODEL
            if _GLOBAL_YOLO_MODEL is None:
                print("[TASK] Loading YOLO model for summarization...")
                # Note: path assumes the model is downloaded or exists in the expected location
                _GLOBAL_YOLO_MODEL = load_model(path="yolov8s.pt", use_gpu=True)
                
            cap = cv2.VideoCapture(tmp_src_path)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open video: {tmp_src_path}")
            
            # Simple frame skip logic for summarization
            frame_skip = 5 
            motion = MotionFilter(threshold=25, min_area=800, adaptive=True)
            
            saved_id = 0
            total_seen = 0
            frame_idx = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                total_seen += 1
                if frame_idx % frame_skip != 0:
                    frame_idx += 1
                    continue
                    
                if motion.is_motion(frame):
                    path = save_frame(base_output, camera_id, saved_id, frame, blur_faces=False)
                    if path:
                        saved_id += 1
                        
                frame_idx += 1
                
            cap.release()
            print(f"[TASK] Found {saved_id} motion frames out of {total_seen} total frames.")
            
            if saved_id == 0:
                print(f"[TASK] No motion detected, skipping object detection.")
                # We could create an empty video or fail, let's just create an empty video for now
                final_video_path = os.path.join(summary_dir, "final_summary.mp4")
                # Create a blank 1 second video
                out = cv2.VideoWriter(final_video_path, cv2.VideoWriter_fourcc(*"mp4v"), 1, (640, 480))
                out.write(cv2.resize(frame, (640, 480)))
                out.release()
            else:
                from object_detection import detect_and_filter
                # Run YOLO detection
                detect_and_filter(
                    frames_dir=selected_dir,
                    output_dir=detected_dir,
                    model=_GLOBAL_YOLO_MODEL,
                    conf=0.5,
                    allowed=None, # Allow all detected objects by default, or limit to person/car
                    batch_size=16,
                    log_detections=False,
                    cam_id=camera_id
                )
                
                final_video_path = os.path.join(summary_dir, "final_summary.mp4")
                # Compile to video
                frames_to_video(
                    frames_dir=detected_dir,
                    output_path=final_video_path,
                    fps=12,
                    cam_id=camera_id,
                    codec="mp4v",
                    crf=23
                )
                
            # Upload final video back to MinIO
            dest_object_name = f"{camera_id}/{summary_id}_summary.mp4"
            ensure_bucket(minio, "camera-summaries")
            
            print(f"[TASK] Uploading summary to MinIO: {dest_object_name}")
            minio.fput_object(
                bucket_name="camera-summaries",
                object_name=dest_object_name,
                file_path=final_video_path,
                content_type="video/mp4"
            )
            
            # Update DB
            update_summary_status(summary_id, "completed", dest_object_name)
            
            try:
                os.unlink(tmp_src_path)
            except:
                pass
                
            print(f"[TASK] Summarization completed for {summary_id}")
            return {"status": "completed", "summary_path": dest_object_name}
            
    except Exception as e:
        print(f"[ERROR] Summarization failed for {summary_id}: {e}")
        update_summary_status(summary_id, "failed")
        raise
