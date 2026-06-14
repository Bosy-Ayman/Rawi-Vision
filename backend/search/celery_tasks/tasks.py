"""
Celery background tasks for the search module.

Task 1: index_video_task
    - Downloads the video from MinIO
    - Runs FrameEncoder (YOLOv8 + EasyOCR + SmolVLM + SentenceTransformer)
    - Inserts 1152-dim frame embeddings into PostgreSQL (pgvector)
    - Updates IndexedVideo status to 'completed' or 'failed'

Task 2: extract_clip_task
    - Downloads the video from MinIO
    - Uses OpenCV to extract a 6-second clip around a target timestamp
    - Uploads the clip back to MinIO under 'extracted-search-clips'

Task 3: record_and_index_task
    - Records from a camera RTSP stream in rolling chunks
    - Uploads each chunk to MinIO and auto-dispatches index_video_task
"""

import os
import sys

# Limit CPU threads to prevent CPU spikes and supervisor container kills
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["DISABLE_TQDM"] = "1"

try:
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
except Exception:
    pass

try:
    import cv2
    cv2.setNumThreads(1)
except Exception:
    pass

from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
import io
import gc
import uuid
import time
import json
import tempfile
import psycopg2
from typing import Optional

# ----------------------------------------------------------------------
# Import the SHARED Celery app from utils.celery_client so this worker
# and the FastAPI router use the exact same app instance + broker config.
# This is what fixes tasks being sent but never received.
# ----------------------------------------------------------------------
from utils.celery_client import celery_app


# ----------------------------------------------------------------------
# Redis helper — defined FIRST so every task below can call it
# ----------------------------------------------------------------------

def get_redis_client():
    import redis
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )


# ----------------------------------------------------------------------
# Queue routing — all three tasks go through the default "celery" queue
# so the worker picks them up without needing extra -Q flags.
# If you later want dedicated queues, add -Q indexing_queue etc. to the
# worker start command AND update task_routes here consistently.
# ----------------------------------------------------------------------
celery_app.conf.task_routes = {
    "search.tasks.index_video_task":        {"queue": "celery"},
    "search.tasks.extract_clip_task":       {"queue": "celery"},
    "search.tasks.record_and_index_task":   {"queue": "celery"},
}


# ----------------------------------------------------------------------
# DB helper — uses psycopg2 directly (Celery workers are sync)
# ----------------------------------------------------------------------

def get_sync_db_conn():
    host = os.getenv("DB_HOST", "localhost")
    if host == "localhost":
        host = "127.0.0.1"  # Force IPv4 to avoid psycopg2 ::1 issues on Windows
    return psycopg2.connect(
        host=host,
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "rawivision_db"),
        user=os.getenv("DB_USER", "shahd"),
        password=os.getenv("DB_PASSWORD", "password")
    )


def update_video_status(video_id: str, status: str):
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE indexed_videos SET status = %s WHERE id = %s",
                (status, video_id)
            )
        conn.commit()
    finally:
        conn.close()


def insert_frame(video_id: str, frame_number: int, timestamp_offset: float,
                 description: str, tracks: str, embedding: list, face_detections_json: str = None):
    """Inserts a single video frame row into video_frames table."""
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO video_frames
                    (video_id, frame_number, timestamp_offset, description, tracks, embedding, face_detections)
                VALUES (%s, %s, %s, %s, %s, %s::vector, %s)
                """,
                (video_id, frame_number, timestamp_offset, description, tracks, json.dumps(embedding), face_detections_json)
            )
        conn.commit()
    finally:
        conn.close()


def insert_video_appearance(video_id: str, employee_id: str, frame_number: int,
                             timestamp_offset: float, confidence: float):
    """Inserts one row into video_appearances for every detected face in a frame.

    This enables continuous per-frame tracking of identified persons in a video,
    so a person appearing in 100 frames produces 100 distinct rows.
    """
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO video_appearances
                    (video_id, employee_id, frame_number, timestamp_offset, confidence)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (video_id, employee_id, frame_number, timestamp_offset, confidence)
            )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------------
# MinIO helper — sync downloads
# ----------------------------------------------------------------------

def get_minio_client():
    from minio import Minio
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


# ----------------------------------------------------------------------
# Task 1: index_video_task — Full ML indexing pipeline
# ----------------------------------------------------------------------

_GLOBAL_ENCODER = None


@celery_app.task(bind=True, name="search.tasks.index_video_task", max_retries=1)
def index_video_task(self, video_id: str, storage_path: str, sampling_rate: int = 16, enable_face_recognition: bool = True):
    """
    Downloads video from MinIO, extracts frame embeddings using FrameEncoder,
    and stores them in PostgreSQL. Optionally inserts face detection data.
    """
    import cv2
    import sys

    print(f"[TASK] Starting video indexing for video_id={video_id}")
    print(f"[TASK] Face recognition: {'ENABLED' if enable_face_recognition else 'DISABLED'}")
    update_video_status(video_id, "indexing")

    redis_client = get_redis_client()

    try:
        minio = get_minio_client()

        bucket_name = "camera-archive-videos"
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        print(f"[TASK] Downloading video from MinIO: {storage_path}")
        minio.fget_object(bucket_name, storage_path, tmp_path)
        print(f"[TASK] Video downloaded to temp: {tmp_path}")

        # Locate ai/search/core and add to sys.path
        backend_dir = Path(__file__).resolve().parent.parent.parent  # backend/
        project_dir = backend_dir.parent                              # project root
        search_core = project_dir / "ai" / "search" / "core"

        if str(search_core) not in sys.path:
            sys.path.insert(0, str(search_core))
        if str(search_core.parent) not in sys.path:
            sys.path.insert(0, str(search_core.parent))

        from offline_index import FrameEncoder

        global _GLOBAL_ENCODER
        if _GLOBAL_ENCODER is None:
            import torch
            device_to_use = "cpu"
            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                try:
                    free_vram, _ = torch.cuda.mem_get_info()
                except Exception:
                    free_vram = (
                        torch.cuda.get_device_properties(0).total_memory
                        - torch.cuda.memory_allocated(0)
                    )
                if free_vram > 2.5 * 1024 ** 3:
                    device_to_use = "cuda"
                else:
                    print(f"[WARN] Low VRAM ({free_vram / 1024**3:.2f} GB free) — using CPU")

            print(f"[TASK] Initializing global FrameEncoder (device={device_to_use})")
            _GLOBAL_ENCODER = FrameEncoder(use_vlm=True, device=device_to_use)
        else:
            print("[TASK] Re-using cached global FrameEncoder")

        encoder = _GLOBAL_ENCODER

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {tmp_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"[TASK] FPS={fps:.1f} | Total frames={total_frames} | Sampling every {sampling_rate} frames")

        # Init Redis progress tracking
        progress_key = f"indexing:progress:{video_id}"
        try:
            redis_client.hset(progress_key, mapping={
                "progress_percent": "0",
                "frames_processed": "0",
                "total_frames": str(total_frames)
            })
            redis_client.expire(progress_key, 3600)
        except Exception as e:
            print(f"[WARN] Failed to init Redis progress: {e}")

        # Store task_id so the video can be revoked on delete
        try:
            redis_client.set(f"indexing:task_id:{video_id}", self.request.id)
            redis_client.expire(f"indexing:task_id:{video_id}", 86400)
        except Exception as e:
            print(f"[WARN] Failed to store task_id in Redis: {e}")

        indexed_frame = 0
        sampled_count = 0
        prev_frame = None
        start = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            indexed_frame += 1
            if indexed_frame % sampling_rate != 0:
                prev_frame = frame
                continue

            sampled_count += 1
            timestamp = indexed_frame / fps

            try:
                embedding, full_desc, track_ids, face_detections = encoder.encode_frame(frame, prev_frame)
                tracks_str = ",".join(map(str, track_ids))
                face_detections_json = json.dumps(face_detections) if face_detections else None

                insert_frame(
                    video_id=video_id,
                    frame_number=indexed_frame,
                    timestamp_offset=timestamp,
                    description=full_desc,
                    tracks=tracks_str,
                    embedding=embedding.tolist(),
                    face_detections_json=face_detections_json
                )

                # Persist every face detection as a separate video_appearances row
                if enable_face_recognition:
                    for det in face_detections:
                        try:
                            insert_video_appearance(
                                video_id=video_id,
                                employee_id=det["emp_id"],
                                frame_number=indexed_frame,
                                timestamp_offset=timestamp,
                                confidence=det["confidence"]
                            )
                        except Exception as app_err:
                            print(f"[WARN] video_appearance insert failed: {app_err}")

                if sampled_count % 5 == 0 or indexed_frame >= total_frames:
                    try:
                        total_sampled = max(1, total_frames // sampling_rate)
                        pct = min(100, int((sampled_count / total_sampled) * 100))
                        redis_client.hset(progress_key, mapping={
                            "progress_percent": str(pct),
                            "frames_processed": str(sampled_count),
                            "total_frames": str(total_frames)
                        })
                    except Exception:
                        pass

                if sampled_count % 10 == 0:
                    print(f"[TASK] Frame {indexed_frame}/{total_frames} @ {timestamp:.2f}s | {full_desc[:60]}...")

            except Exception as frame_err:
                print(f"[WARN] Frame {indexed_frame} encoding failed: {frame_err}")

            prev_frame = frame

        cap.release()

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        elapsed = round(time.time() - start, 1)
        print(f"[TASK] Indexing complete: {sampled_count} frames in {elapsed}s for video_id={video_id}")

        try:
            redis_client.hset(progress_key, "progress_percent", "100")
            redis_client.delete(f"indexing:task_id:{video_id}")
        except Exception:
            pass

        update_video_status(video_id, "completed")
        return {"status": "completed", "frames_indexed": sampled_count, "elapsed_seconds": elapsed}

    except Exception as e:
        print(f"[ERROR] index_video_task failed for video_id={video_id}: {e}")
        update_video_status(video_id, "failed")

        err_msg = str(e).lower()
        if "nosuchkey" in err_msg or "does not exist" in err_msg:
            print(f"[ERROR] Object {storage_path} not found in MinIO. Skipping retry.")
            try:
                redis_client.delete(f"indexing:task_id:{video_id}")
            except Exception:
                pass
            return {"status": "failed", "error": "file_not_found"}

        raise self.retry(exc=e, countdown=10)


# ----------------------------------------------------------------------
# Task 2: extract_clip_task — Cut 6s clips and upload to MinIO
# ----------------------------------------------------------------------

@celery_app.task(bind=True, name="search.tasks.extract_clip_task")
def extract_clip_task(self, video_id: str, storage_path: str, frame_number: int,
                      timestamp_offset: float, clip_duration: float = 6.0, draw_bboxes: bool = True):
    """
    Cuts a short clip centred on timestamp_offset and uploads it to MinIO.
    Optionally draws face bounding boxes on frames.
    """
    import cv2

    print(f"[TASK] Extracting clip for frame {frame_number} @ {timestamp_offset:.2f}s in video {video_id}")

    try:
        minio = get_minio_client()

        bucket_name = "camera-archive-videos"
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            src_tmp_path = tmp_file.name
        minio.fget_object(bucket_name, storage_path, src_tmp_path)

        cap = cv2.VideoCapture(src_tmp_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video for clip extraction: {src_tmp_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Get frame data for bbox drawing if enabled
        frame_bbox_map = {}
        if draw_bboxes:
            try:
                conn = get_sync_db_conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT frame_number, face_detections FROM video_frames WHERE video_id = %s",
                        (video_id,)
                    )
                    for row in cur.fetchall():
                        frame_num = row[0]
                        face_detections_json = row[1]
                        if face_detections_json:
                            frame_bbox_map[frame_num] = json.loads(face_detections_json)
                conn.close()
            except Exception as e:
                print(f"[WARN] Failed to fetch bbox data: {e}")

        half_dur = clip_duration / 2.0
        start_time = max(0.0, timestamp_offset - half_dur)
        end_time = min(total_frames / fps, timestamp_offset + half_dur)
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)

        target_height = 720
        aspect_ratio = width / height if height > 0 else 16 / 9
        target_width = int(target_height * aspect_ratio)
        if target_width % 2 != 0:
            target_width += 1

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as clip_tmp:
            clip_tmp_path = clip_tmp.name

        fourcc = cv2.VideoWriter_fourcc(*"VP80")
        out_writer = cv2.VideoWriter(clip_tmp_path, fourcc, fps, (target_width, target_height))

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame = start_frame
        scale_x = target_width / width if width > 0 else 1
        scale_y = target_height / height if height > 0 else 1

        past_frames = [f for f in frame_bbox_map.keys() if f <= start_frame]
        last_drawn_bboxes = frame_bbox_map[max(past_frames)] if past_frames else []

        while current_frame <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            resized_frame = cv2.resize(frame, (target_width, target_height))

            # Draw bounding boxes if available for this frame
            if draw_bboxes:
                if current_frame in frame_bbox_map:
                    last_drawn_bboxes = frame_bbox_map[current_frame]
                    
                for det in last_drawn_bboxes:
                    try:
                        x1, y1, x2, y2 = int(det["x1"] * scale_x), int(det["y1"] * scale_y), int(det["x2"] * scale_x), int(det["y2"] * scale_y)
                        name = det.get("name", "Unknown")
                        conf = det.get("confidence", 0)
                        is_unknown = det.get("is_unknown", False)

                        # Red for unknown, green for identified
                        color = (0, 0, 255) if is_unknown else (0, 255, 0)

                        cv2.rectangle(resized_frame, (x1, y1), (x2, y2), color, 2)
                        label = f"{name} ({conf:.2f})"
                        cv2.putText(resized_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    except Exception as bbox_err:
                        print(f"[WARN] Failed to draw bbox: {bbox_err}")

            out_writer.write(resized_frame)
            current_frame += 1

        cap.release()
        out_writer.release()

        clip_object_name = (
            f"extracted_clips/{video_id}/clip_frame_{frame_number}_{timestamp_offset:.2f}s.webm"
        )
        ensure_bucket(minio, "extracted-search-clips")
        minio.fput_object(
            bucket_name="extracted-search-clips",
            object_name=clip_object_name,
            file_path=clip_tmp_path,
            content_type="video/webm"
        )

        print(f"[TASK] Clip uploaded to MinIO: {clip_object_name}")

        for p in [src_tmp_path, clip_tmp_path]:
            try:
                os.unlink(p)
            except Exception:
                pass

        return {"clip_object_name": clip_object_name}

    except Exception as e:
        print(f"[ERROR] extract_clip_task failed: {e}")
        raise


# ----------------------------------------------------------------------
# Task 3: record_and_index_task — Rolling RTSP recorder + auto-indexing
# ----------------------------------------------------------------------

def lookup_rtsp_urls(camera_id: str) -> list:
    """Looks up RTSP URLs for a camera via psycopg2 (sync)."""
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cm.rtsp_urls
                FROM cameras c
                JOIN camera_metadata cm ON c.mac_address = cm.mac_address
                WHERE c.id = %s
                LIMIT 1
                """,
                (camera_id,)
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"No camera_metadata found for camera_id={camera_id}")
            urls = row[0]
            if isinstance(urls, str):
                urls = json.loads(urls)
            return urls
    finally:
        conn.close()


def create_indexed_video_record(video_id: str, camera_id: str, storage_path: str,
                                filename: str, sampling_rate: int):
    """Creates an IndexedVideo row directly via psycopg2 (sync)."""
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO indexed_videos
                    (id, camera_id, storage_path, filename, status, sampling_rate)
                VALUES (%s, %s, %s, %s, 'pending', %s)
                """,
                (video_id, camera_id, storage_path, filename, sampling_rate)
            )
        conn.commit()
    finally:
        conn.close()

def create_video_summary_record(summary_id: str, video_id: str, camera_id: str, generation_type: str):
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO video_summaries
                    (id, video_id, camera_id, status, generation_type)
                VALUES (%s, %s, %s, 'pending', %s)
                """,
                (summary_id, video_id, camera_id, generation_type)
            )
        conn.commit()
    finally:
        conn.close()


@celery_app.task(bind=True, name="search.tasks.record_and_index_task")
def record_and_index_task(self, camera_id: str, duration: int = 600,
                          chunk_size: int = 300, sampling_rate: int = 16,
                          burn_bboxes: bool = False):
    """
    Records from a camera RTSP stream in rolling chunks, uploads each chunk
    to MinIO, and auto-dispatches index_video_task per chunk.
    Stoppable via Redis key: stop:record:{camera_id}
    """
    import cv2

    redis_client = get_redis_client()
    redis_key = f"stop:record:{camera_id}"
    status_key = f"recording:status:{camera_id}"

    print(f"[RECORD] Starting recording for camera_id={camera_id} | duration={duration}s | chunk_size={chunk_size}s | burn_bboxes={burn_bboxes}")

    redis_client.hset(status_key, mapping={
        "status": "recording",
        "camera_id": camera_id,
        "chunks_recorded": "0",
        "start_time": str(int(time.time()))
    })

    # AI Overlay models initialization
    annotator_yolo_person = None
    annotator_tracker = None
    annotator_yolo_face = None
    annotator_resnet = None
    annotator_face_manager = None

    if burn_bboxes:
        try:
            import torch
            from ultralytics import YOLO
            from boxmot.trackers.tracker_zoo import create_tracker
            from facenet_pytorch import InceptionResnetV1
            import sys
            
            # Setup path to load EmbeddingManager
            backend_dir = Path(__file__).resolve().parent.parent.parent
            project_dir = backend_dir.parent
            search_core = project_dir / "ai" / "search" / "core"
            if str(search_core) not in sys.path:
                sys.path.insert(0, str(search_core))
            from embedding_manager import EmbeddingManager
            
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            weights_dir = project_dir / "backend" / "camera_ingestion" / "ai" / "weights"
            
            print(f"[RECORD-AI] Loading YOLO person and tracking models on {device}...")
            annotator_yolo_person = YOLO(str(weights_dir / "yolov8n.pt")).to(device)
            annotator_tracker = create_tracker(
                tracker_type="strongsort",
                reid_weights=weights_dir / "osnet_x0_25_msmt17.pt",
                device=device,
                half=device == "cuda:0"
            )
            
            try:
                annotator_yolo_face = YOLO(str(weights_dir / "yolov12m-face.pt")).to(device)
                annotator_resnet = InceptionResnetV1(pretrained="vggface2").to(device).eval()
                annotator_face_manager = EmbeddingManager(db_config=os.getenv("DATABASE_URL"))
                annotator_face_manager.load_db_into_memory()
                print("[RECORD-AI] Face recognition models loaded successfully.")
            except Exception as fe:
                print(f"[RECORD-AI] Warning: Face recognition sub-models failed to load: {fe}")
        except Exception as e:
            print(f"[RECORD-AI] Error initializing AI Overlay: {e}. Falling back to raw recording.")
            burn_bboxes = False

    try:
        rtsp_urls = lookup_rtsp_urls(camera_id)
        print(f"[RECORD] Found RTSP URLs: {rtsp_urls}")

        cap = None
        for url in rtsp_urls:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                print(f"[RECORD] Connected to RTSP stream: {url}")
                break

        if cap is None or not cap.isOpened():
            print(f"[RECORD] Could not open any RTSP stream. Falling back to mock video.")
            mock_video_path = r"c:\Users\pouss\Documents\CSAI\Rawi-Vision\ai\search\videos\shoplifting.mp4"
            cap = cv2.VideoCapture(mock_video_path)
            if not cap.isOpened():
                raise RuntimeError(f"Could not open mock video: {mock_video_path}")
            print(f"[RECORD] Mock video stream opened: {mock_video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        minio = get_minio_client()
        ensure_bucket(minio, "camera-archive-videos")

        total_start = time.time()
        chunks_recorded = 0

        while (time.time() - total_start) < duration:
            if redis_client.get(redis_key):
                print(f"[RECORD] Stop signal received for camera {camera_id}")
                break

            chunk_id = str(uuid.uuid4())
            chunk_timestamp = int(time.time())
            chunk_filename = f"{camera_id}_{chunk_timestamp}.webm"
            storage_path = f"{camera_id}/{chunk_filename}"

            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_file:
                tmp_path = tmp_file.name

            fourcc = cv2.VideoWriter_fourcc(*"VP80")
            out_writer = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))

            chunk_start = time.time()
            frames_in_chunk = 0
            print(f"[RECORD] Recording chunk #{chunks_recorded + 1}: {chunk_filename}")

            while (time.time() - chunk_start) < chunk_size:
                if redis_client.get(redis_key):
                    print(f"[RECORD] Stop signal received mid-chunk for camera {camera_id}")
                    break

                ret, frame = cap.read()
                if not ret:
                    print(f"[WARN] Lost RTSP stream, attempting reconnect...")
                    cap.release()
                    time.sleep(2)
                    for url in rtsp_urls:
                        cap = cv2.VideoCapture(url)
                        if cap.isOpened():
                            break
                    if not cap.isOpened():
                        print(f"[ERROR] Could not reconnect to RTSP stream")
                        break
                    continue

                if burn_bboxes and annotator_yolo_person is not None:
                    try:
                        import torch
                        results = annotator_yolo_person(frame, classes=0, verbose=False, conf=0.5)
                        prev_dets = (
                            results[0].boxes.data.cpu().numpy()
                            if len(results[0].boxes) > 0
                            else np.empty((0, 6))
                        )
                        
                        if prev_dets.shape[0] > 0:
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            tracks = annotator_tracker.update(prev_dets, rgb)
                            for track in tracks:
                                tx1, ty1, tx2, ty2, track_id = map(int, track[:5])
                                tx1, ty1 = max(0, tx1), max(0, ty1)
                                tx2, ty2 = min(width, tx2), min(height, ty2)
                                
                                name = "Unknown"
                                if annotator_yolo_face is not None:
                                    person_crop = frame[ty1:ty2, tx1:tx2]
                                    if person_crop.size > 0:
                                        face_res = annotator_yolo_face(person_crop, verbose=False, conf=0.3)
                                        for fr in face_res:
                                            for box in fr.boxes:
                                                fx1, fy1, fx2, fy2 = map(int, box.xyxy[0])
                                                ph, pw = person_crop.shape[:2]
                                                fx1, fy1 = max(0, fx1), max(0, fy1)
                                                fx2, fy2 = min(pw, fx2), min(ph, fy2)
                                                face_crop = person_crop[fy1:fy2, fx1:fx2]
                                                if face_crop.size > 0:
                                                    face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                                                    face_resized = cv2.resize(face_rgb, (160, 160))
                                                    face_norm = face_resized.astype(np.float32) / 255.0
                                                    face_norm = (face_norm - 0.5) / 0.5
                                                    face_tensor = torch.tensor(np.transpose(face_norm, (2, 0, 1))).unsqueeze(0).to(device)
                                                    with torch.no_grad():
                                                        emb = annotator_resnet(face_tensor).cpu().numpy().squeeze()
                                                    # search_face returns (name, emp_id, dist)
                                                    db_name, emp_id, dist = annotator_face_manager.search_face(emb)
                                                    if dist < 1.0 and db_name != "Unknown":
                                                        name = db_name
                                                        break
                                
                                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                                cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), color, 2)
                                cv2.putText(frame, f"{name} ID:{track_id}",
                                            (tx1, ty1 - 10),
                                            cv2.FONT_HERSHEY_SIMPLEX,
                                            0.6, color, 2)
                    except Exception as loop_ai_err:
                        # Fall back gracefully so recording doesn't crash
                        pass

                out_writer.write(frame)
                frames_in_chunk += 1


            out_writer.release()

            if frames_in_chunk == 0:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                continue

            print(f"[RECORD] Uploading chunk to MinIO: {storage_path} ({frames_in_chunk} frames)")
            minio.fput_object(
                bucket_name="camera-archive-videos",
                object_name=storage_path,
                file_path=tmp_path,
                content_type="video/webm"
            )

            create_indexed_video_record(
                video_id=chunk_id,
                camera_id=camera_id,
                storage_path=storage_path,
                filename=chunk_filename,
                sampling_rate=sampling_rate
            )

            index_video_task.delay(chunk_id, storage_path, sampling_rate)
            print(f"[RECORD] Indexing task dispatched for chunk {chunk_id}")

            try:
                auto_summarize = redis_client.get("auto_summarize_enabled")
                if auto_summarize and auto_summarize.lower() == "true":
                    summary_id = str(uuid.uuid4())
                    create_video_summary_record(summary_id, chunk_id, camera_id, "auto")
                    celery_app.send_task(
                        "summarization.tasks.generate_video_summary_task",
                        args=[summary_id, chunk_id, camera_id, storage_path]
                    )
                    print(f"[RECORD] Auto-Summarization task dispatched for chunk {chunk_id}")
            except Exception as sum_err:
                print(f"[WARN] Failed to trigger auto-summarization: {sum_err}")

            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            chunks_recorded += 1
            redis_client.hset(status_key, "chunks_recorded", str(chunks_recorded))

            if (time.time() - total_start) >= duration:
                break

        cap.release()

        elapsed = round(time.time() - total_start, 1)
        print(f"[RECORD] Recording complete: {chunks_recorded} chunks in {elapsed}s for camera {camera_id}")

        redis_client.hset(status_key, mapping={
            "status": "completed",
            "chunks_recorded": str(chunks_recorded),
            "elapsed_seconds": str(elapsed)
        })
        redis_client.expire(status_key, 3600)
        try:
            redis_client.delete(redis_key)
        except Exception:
            pass

        return {
            "status": "completed",
            "camera_id": camera_id,
            "chunks_recorded": chunks_recorded,
            "elapsed_seconds": elapsed
        }

    except Exception as e:
        print(f"[ERROR] record_and_index_task failed for camera {camera_id}: {e}")
        redis_client.hset(status_key, mapping={
            "status": "failed",
            "error": str(e)
        })
        redis_client.expire(status_key, 3600)
        raise