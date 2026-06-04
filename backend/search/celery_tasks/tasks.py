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
"""

import os
import io
import gc
import uuid
import time
import json
import tempfile
import psycopg2
from pathlib import Path
from typing import Optional
from celery import Celery

# Celery app is initialized from the existing project broker
celery_app = Celery(
    "search_tasks",
    broker=os.getenv("BROKER_URL", "amqp://guest:guest@127.0.0.1:5672//"),
    backend=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/1"
)

# ----------------------------------------------------------------------
# DB helper — uses psycopg2 directly (Celery workers are sync)
# ----------------------------------------------------------------------

def get_sync_db_conn():
    host = os.getenv("DB_HOST", "localhost")
    if host == "localhost":
        host = "127.0.0.1"  # Force IPv4 to prevent psycopg2 Software caused connection abort on ::1
        
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
                 description: str, tracks: str, embedding: list):
    """Inserts a single video frame row into video_frames table."""
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO video_frames (video_id, frame_number, timestamp_offset, description, tracks, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                """,
                (video_id, frame_number, timestamp_offset, description, tracks, json.dumps(embedding))
            )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------------
# MinIO helper — sync downloads
# ----------------------------------------------------------------------

def get_minio_client():
    from minio import Minio
    minio_url = os.getenv("MINIO_SERVER_URL", "127.0.0.1:9000").replace("http://", "").replace("https://", "")
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

@celery_app.task(bind=True, name="search.tasks.index_video_task", max_retries=1)
def index_video_task(self, video_id: str, storage_path: str, sampling_rate: int = 16):
    """
    Downloads video from MinIO, extracts frame embeddings using the FrameEncoder
    from ai/search/core/offline_index.py, and stores them in PostgreSQL.

    Args:
        video_id: UUID string of the IndexedVideo record
        storage_path: MinIO object key (e.g. 'camera-archive-videos/uuid.mp4')
        sampling_rate: Analyze every N-th frame (default 16)
    """
    import cv2
    import sys

    print(f"[TASK] Starting video indexing for video_id={video_id}")
    update_video_status(video_id, "indexing")

    try:
        minio = get_minio_client()

        # Download video to a temp file — needed since OpenCV reads from file paths
        bucket_name = "camera-archive-videos"
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        print(f"[TASK] Downloading video from MinIO: {storage_path}")
        minio.fget_object(bucket_name, storage_path, tmp_path)
        print(f"[TASK] Video downloaded to temp: {tmp_path}")

        # Dynamically import FrameEncoder from ai/search/core/offline_index.py
        # Walk up directories to locate the ai/search/core path
        backend_dir = Path(__file__).resolve().parent.parent.parent  # backend/
        project_dir = backend_dir.parent                              # project root
        search_core = project_dir / "ai" / "search" / "core"

        if str(search_core) not in sys.path:
            sys.path.insert(0, str(search_core))
        if str(search_core.parent) not in sys.path:
            sys.path.insert(0, str(search_core.parent))

        from offline_index import FrameEncoder

        # Check GPU availability — fallback to CPU if VRAM is heavily used
        import torch
        device_to_use = "cpu"
        if torch.cuda.is_available():
            free_vram = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
            # Only use GPU if more than 2GB VRAM is free
            if free_vram > 2 * 1024 ** 3:
                device_to_use = "cuda"
            else:
                print("[WARN] GPU VRAM heavily occupied — falling back to CPU for indexing")

        print(f"[TASK] Initializing FrameEncoder on device: {device_to_use}")
        encoder = FrameEncoder(use_vlm=(device_to_use == "cuda"))

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {tmp_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"[TASK] FPS={fps:.1f} | Total frames={total_frames} | Sampling every {sampling_rate} frames")

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
                embedding, full_desc, track_ids = encoder.encode_frame(frame, prev_frame)
                tracks_str = ",".join(map(str, track_ids))

                # Insert into postgres
                insert_frame(
                    video_id=video_id,
                    frame_number=indexed_frame,
                    timestamp_offset=timestamp,
                    description=full_desc,
                    tracks=tracks_str,
                    embedding=embedding.tolist()
                )

                if sampled_count % 10 == 0:
                    print(f"[TASK] [{sampled_count}] Frame {indexed_frame}/{total_frames} @ {timestamp:.2f}s | {full_desc[:60]}...")
            except Exception as frame_err:
                print(f"[WARN] Frame {indexed_frame} encoding failed: {frame_err}")

            prev_frame = frame

        cap.release()

        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        # Clean up model memory
        import torch
        del encoder
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        elapsed = round(time.time() - start, 1)
        print(f"[TASK] Indexing complete: {sampled_count} frames in {elapsed}s for video_id={video_id}")
        update_video_status(video_id, "completed")
        return {"status": "completed", "frames_indexed": sampled_count, "elapsed_seconds": elapsed}

    except Exception as e:
        print(f"[ERROR] index_video_task failed for video_id={video_id}: {e}")
        update_video_status(video_id, "failed")
        raise self.retry(exc=e, countdown=10)


# ----------------------------------------------------------------------
# Task 2: extract_clip_task — Cut 6s clips and upload to MinIO
# ----------------------------------------------------------------------

@celery_app.task(bind=True, name="search.tasks.extract_clip_task")
def extract_clip_task(self, video_id: str, storage_path: str, frame_number: int,
                      timestamp_offset: float, clip_duration: float = 6.0):
    """
    Cuts a short clip of 'clip_duration' seconds centred on 'timestamp_offset'
    from the original video in MinIO and uploads the result to
    'extracted-search-clips' bucket.

    Args:
        video_id: UUID string of the IndexedVideo record
        storage_path: MinIO source object key
        frame_number: Frame number of the match (used in output filename)
        timestamp_offset: Time in seconds of the match within the video
        clip_duration: Length of clip in seconds (default 6)
    """
    import cv2

    print(f"[TASK] Extracting clip for frame {frame_number} @ {timestamp_offset:.2f}s in video {video_id}")

    try:
        minio = get_minio_client()

        # Download source video to temp file
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

        half_dur = clip_duration / 2.0
        start_time = max(0.0, timestamp_offset - half_dur)
        end_time = min(total_frames / fps, timestamp_offset + half_dur)
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)

        # Write clip to a second temp file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as clip_tmp:
            clip_tmp_path = clip_tmp.name

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out_writer = cv2.VideoWriter(clip_tmp_path, fourcc, fps, (width, height))

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame = start_frame
        while current_frame <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            out_writer.write(frame)
            current_frame += 1

        cap.release()
        out_writer.release()

        # Upload clip to MinIO
        clip_object_name = f"extracted_clips/{video_id}/clip_frame_{frame_number}_{timestamp_offset:.2f}s.mp4"
        ensure_bucket(minio, "extracted-search-clips")
        minio.fput_object(
            bucket_name="extracted-search-clips",
            object_name=clip_object_name,
            file_path=clip_tmp_path,
            content_type="video/mp4"
        )

        print(f"[TASK] Clip uploaded to MinIO: {clip_object_name}")

        # Clean up temp files
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

def get_redis_client():
    import redis
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )


def lookup_rtsp_urls(camera_id: str) -> list:
    """
    Looks up RTSP URLs for a camera by joining cameras → camera_metadata.
    cameras.id (UUID) → cameras.mac_address → camera_metadata.mac_address → rtsp_urls (JSON).
    Uses psycopg2 since Celery workers are synchronous.
    """
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
            # rtsp_urls is stored as JSON array in PostgreSQL
            urls = row[0]
            if isinstance(urls, str):
                urls = json.loads(urls)
            return urls
    finally:
        conn.close()


def create_indexed_video_record(video_id: str, camera_id: str, storage_path: str,
                                 filename: str, sampling_rate: int):
    """Creates an IndexedVideo row directly via psycopg2 (sync, for Celery)."""
    conn = get_sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO indexed_videos (id, camera_id, storage_path, filename, status, sampling_rate)
                VALUES (%s, %s, %s, %s, 'pending', %s)
                """,
                (video_id, camera_id, storage_path, filename, sampling_rate)
            )
        conn.commit()
    finally:
        conn.close()


@celery_app.task(bind=True, name="search.tasks.record_and_index_task")
def record_and_index_task(self, camera_id: str, duration: int = 600,
                          chunk_size: int = 300, sampling_rate: int = 16):
    """
    Records from a camera's RTSP stream in rolling chunks, uploads each chunk
    to MinIO, creates an IndexedVideo record, and auto-dispatches
    index_video_task for each chunk.

    Stoppable via Redis key: stop:record:{camera_id}

    Args:
        camera_id: UUID string of the camera (from 'cameras' table)
        duration: Total recording duration in seconds (default 600 = 10 min)
        chunk_size: Duration of each chunk in seconds (default 300 = 5 min)
        sampling_rate: Frame sampling rate for indexing (default 16)
    """
    import cv2

    redis_client = get_redis_client()
    redis_key = f"stop:record:{camera_id}"
    status_key = f"recording:status:{camera_id}"

    print(f"[RECORD] Starting recording for camera_id={camera_id} | duration={duration}s | chunk_size={chunk_size}s")

    # Mark recording as active in Redis
    redis_client.hset(status_key, mapping={
        "status": "recording",
        "camera_id": camera_id,
        "chunks_recorded": "0",
        "start_time": str(int(time.time()))
    })

    try:
        # Look up RTSP URLs from the database
        rtsp_urls = lookup_rtsp_urls(camera_id)
        print(f"[RECORD] Found RTSP URLs: {rtsp_urls}")

        # Try each RTSP URL until one opens
        cap = None
        for url in rtsp_urls:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                print(f"[RECORD] Connected to RTSP stream: {url}")
                break
        if cap is None or not cap.isOpened():
            raise RuntimeError(f"Could not open any RTSP stream for camera {camera_id}: {rtsp_urls}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        minio = get_minio_client()
        ensure_bucket(minio, "camera-archive-videos")

        total_start = time.time()
        chunks_recorded = 0

        while (time.time() - total_start) < duration:
            # Check for stop signal
            if redis_client.get(redis_key):
                print(f"[RECORD] Stop signal received for camera {camera_id}")
                redis_client.delete(redis_key)
                break

            # Start a new chunk
            chunk_id = str(uuid.uuid4())
            chunk_timestamp = int(time.time())
            chunk_filename = f"{camera_id}_{chunk_timestamp}.mp4"
            storage_path = f"{camera_id}/{chunk_filename}"

            # Write chunk to a temp file
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
                tmp_path = tmp_file.name

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out_writer = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))

            chunk_start = time.time()
            frames_in_chunk = 0
            print(f"[RECORD] Recording chunk #{chunks_recorded + 1}: {chunk_filename}")

            while (time.time() - chunk_start) < chunk_size:
                # Check stop signal mid-chunk
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

                out_writer.write(frame)
                frames_in_chunk += 1

            out_writer.release()

            if frames_in_chunk == 0:
                # Empty chunk — skip upload
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                continue

            # Upload chunk to MinIO
            print(f"[RECORD] Uploading chunk to MinIO: {storage_path} ({frames_in_chunk} frames)")
            minio.fput_object(
                bucket_name="camera-archive-videos",
                object_name=storage_path,
                file_path=tmp_path,
                content_type="video/mp4"
            )

            # Create IndexedVideo DB record
            create_indexed_video_record(
                video_id=chunk_id,
                camera_id=camera_id,
                storage_path=storage_path,
                filename=chunk_filename,
                sampling_rate=sampling_rate
            )

            # Auto-dispatch indexing task for this chunk
            index_video_task.delay(chunk_id, storage_path, sampling_rate)
            print(f"[RECORD] Indexing task dispatched for chunk {chunk_id}")

            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            chunks_recorded += 1
            redis_client.hset(status_key, "chunks_recorded", str(chunks_recorded))

            # Check if total duration has been exceeded
            if (time.time() - total_start) >= duration:
                break

        cap.release()

        elapsed = round(time.time() - total_start, 1)
        print(f"[RECORD] Recording complete: {chunks_recorded} chunks in {elapsed}s for camera {camera_id}")

        # Update Redis status
        redis_client.hset(status_key, mapping={
            "status": "completed",
            "chunks_recorded": str(chunks_recorded),
            "elapsed_seconds": str(elapsed)
        })
        # Expire the status key after 1 hour
        redis_client.expire(status_key, 3600)

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
