"""
FastAPI router for the semantic video search module.

Endpoints:
    POST   /api/search/upload           — Upload a video + queue indexing task
    GET    /api/search/status/{video_id} — Check indexing progress
    POST   /api/search/query            — Run semantic search + LLM reasoning
    GET    /api/search/videos           — List all indexed videos
    DELETE /api/search/video/{video_id} — Delete index and MinIO files
"""

import os
import uuid
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from minio import Minio

from database import get_db, db_dependency
from config import Config
from search.models.search import IndexedVideo, VideoFrame
from camera_onboarding.models.camera import Camera
from search.schemas.search import SearchQueryRequest, SearchQueryResponse, VideoStatusResponse, RecordRequest, RecordingStatusResponse, VideoFrameResponse
from search.services.search_service import SearchService
from search.celery_tasks.tasks import index_video_task, extract_clip_task, record_and_index_task

search_router = APIRouter(prefix="/api/search", tags=["semantic video search"])


def get_redis_client():
    import redis
    return redis.Redis(
        host=Config.REDIS_HOST or "localhost",
        port=int(Config.REDIS_PORT or 6379),
        db=0,
        decode_responses=True
    )


# ----------------------------------------------------------------------
# Dependency: MinIO client
# ----------------------------------------------------------------------

def get_minio() -> Minio:
    minio_url = Config.MINIO_SERVER_URL.replace("http://", "").replace("https://", "")
    return Minio(
        minio_url,
        access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        secure=False
    )


def get_search_service() -> SearchService:
    return SearchService()


# ----------------------------------------------------------------------
# Endpoint 1: Upload Video & Schedule Indexing
# ----------------------------------------------------------------------

@search_router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    db: db_dependency,
    file: UploadFile = File(...),
    camera_id: uuid.UUID = Form(...),
    sampling_rate: int = Form(16),
    minio: Minio = Depends(get_minio)
):
    """
    Accepts a video file upload, saves it to MinIO, creates an IndexedVideo
    record in PostgreSQL with status='pending', then dispatches a Celery
    background task to index the video frames.
    """
    if not file.content_type or "video" not in file.content_type:
        raise HTTPException(status_code=400, detail="Uploaded file must be a video (mp4, avi, mkv, etc.)")

    video_id = uuid.uuid4()
    ext = Path(file.filename).suffix if file.filename else ".mp4"
    storage_path = f"{video_id}{ext}"
    bucket_name = "camera-archive-videos"

    # Ensure bucket exists
    if not minio.bucket_exists(bucket_name):
        minio.make_bucket(bucket_name)

    # Stream upload directly into MinIO without loading entire file into RAM
    file_bytes = await file.read()
    minio.put_object(
        bucket_name=bucket_name,
        object_name=storage_path,
        data=BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=file.content_type or "video/mp4"
    )

    # Create DB record
    indexed_video = IndexedVideo(
        id=video_id,
        camera_id=camera_id,
        storage_path=storage_path,
        filename=file.filename or f"{video_id}{ext}",
        status="pending",
        sampling_rate=sampling_rate
    )
    db.add(indexed_video)
    await db.commit()

    # Dispatch Celery background indexing task
    task = index_video_task.delay(str(video_id), storage_path, sampling_rate)
    try:
        redis_client = get_redis_client()
        redis_client.set(f"indexing:task_id:{video_id}", task.id)
    except Exception as e:
        print(f"[WARN] Failed to save task_id to Redis: {e}")

    return {
        "video_id": str(video_id),
        "status": "pending",
        "message": "Video uploaded successfully. Indexing task queued in background."
    }


# ----------------------------------------------------------------------
# Endpoint 2: Check Indexing Status
# ----------------------------------------------------------------------

@search_router.get("/status/{video_id}", response_model=VideoStatusResponse)
async def get_video_status(video_id: uuid.UUID, db: db_dependency):
    """Returns the current status of a queued or running indexing job."""
    stmt = select(IndexedVideo).filter(IndexedVideo.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found.")

    # Retrieve progress from Redis if indexing
    redis_client = get_redis_client()
    progress_key = f"indexing:progress:{video_id}"
    progress_data = {}
    try:
        progress_data = redis_client.hgetall(progress_key)
    except Exception:
        pass

    progress_percent = 0
    frames_processed = 0
    total_frames = 0
    
    if progress_data:
        progress_percent = int(progress_data.get("progress_percent", 0))
        frames_processed = int(progress_data.get("frames_processed", 0))
        total_frames = int(progress_data.get("total_frames", 0))
    elif video.status == "completed":
        progress_percent = 100

    camera_room = None
    camera_building = None
    camera_number = None

    if video.camera_id and str(video.camera_id) != "00000000-0000-0000-0000-000000000000":
        cam_stmt = select(Camera).filter(Camera.id == video.camera_id)
        cam_result = await db.execute(cam_stmt)
        camera = cam_result.scalar_one_or_none()
        if camera:
            camera_room = camera.room
            camera_building = camera.building
            
            # Stable camera numbering based on creation date
            all_cams_stmt = select(Camera).order_by(Camera.date_created.asc())
            all_cams_result = await db.execute(all_cams_stmt)
            all_cameras = all_cams_result.scalars().all()
            for idx, cam in enumerate(all_cameras):
                if cam.id == camera.id:
                    camera_number = f"Camera {idx + 1}"
                    break

    return VideoStatusResponse(
        video_id=video.id,
        filename=video.filename,
        status=video.status,
        sampling_rate=video.sampling_rate,
        date_created=video.date_created,
        progress_percent=progress_percent,
        frames_processed=frames_processed,
        total_frames=total_frames,
        camera_room=camera_room,
        camera_building=camera_building,
        camera_number=camera_number
    )


# ----------------------------------------------------------------------
# Endpoint 3: Semantic Search Query
# ----------------------------------------------------------------------

@search_router.post("/query", response_model=SearchQueryResponse)
async def query_search(
    request: SearchQueryRequest,
    db: db_dependency,
    service: SearchService = Depends(get_search_service)
):
    try:
        # Ensure the video is indexed before querying
        stmt = select(IndexedVideo).filter(IndexedVideo.id == request.video_id)
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()

        if not video:
            raise HTTPException(status_code=404, detail=f"Video {request.video_id} not found.")

        if video.status != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Video is still being indexed (status='{video.status}'). Please wait until indexing completes."
            )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Run semantic search + identity fusion + LLM reasoning
        search_result = await service.search(
            db=db,
            video_id=request.video_id,
            query=request.query,
            top_k=request.top_k,
            use_llm=request.use_llm
        )

        # Dispatch async clip extraction tasks for each matched frame
        # Clips are uploaded to MinIO and presigned URLs are pre-generated
        for match in search_result["results"]:
            extract_clip_task.delay(
                video_id=str(request.video_id),
                storage_path=video.storage_path,
                frame_number=match["frame_id"],
                timestamp_offset=match["timestamp"],
                clip_duration=6.0
            )

        return {
            "query": search_result["query"],
            "total_results": search_result["total_results"],
            "llm_answer": search_result["llm_answer"],
            "reid_tracks": search_result["reid_tracks"],
            "results": search_result["results"]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------------
# Endpoint 4: List All Indexed Videos
# ----------------------------------------------------------------------

@search_router.get("/videos")
async def list_videos(db: db_dependency):
    """Returns a list of all uploaded and indexed videos with their statuses."""
    stmt = select(IndexedVideo).order_by(IndexedVideo.date_created.desc())
    result = await db.execute(stmt)
    videos = result.scalars().all()

    # Fetch all cameras to construct a map of camera_id -> (room, building, name/number)
    cams_stmt = select(Camera).order_by(Camera.date_created.asc())
    cams_result = await db.execute(cams_stmt)
    all_cameras = cams_result.scalars().all()
    camera_map = {}
    for idx, cam in enumerate(all_cameras):
        camera_map[str(cam.id)] = {
            "room": cam.room,
            "building": cam.building,
            "number": f"Camera {idx + 1}"
        }

    redis_client = get_redis_client()

    results = []
    for v in videos:
        progress_percent = 0
        frames_processed = 0
        total_frames = 0
        if v.status == "indexing":
            progress_key = f"indexing:progress:{v.id}"
            try:
                progress_data = redis_client.hgetall(progress_key)
                if progress_data:
                    progress_percent = int(progress_data.get("progress_percent", 0))
                    frames_processed = int(progress_data.get("frames_processed", 0))
                    total_frames = int(progress_data.get("total_frames", 0))
            except Exception:
                pass
        elif v.status == "completed":
            progress_percent = 100

        cam_info = camera_map.get(str(v.camera_id), {})

        results.append({
            "video_id": str(v.id),
            "camera_id": str(v.camera_id),
            "filename": v.filename,
            "status": v.status,
            "sampling_rate": v.sampling_rate,
            "date_created": v.date_created.isoformat(),
            "progress_percent": progress_percent,
            "frames_processed": frames_processed,
            "total_frames": total_frames,
            "camera_room": cam_info.get("room"),
            "camera_building": cam_info.get("building"),
            "camera_number": cam_info.get("number")
        })
    return results


# ----------------------------------------------------------------------
# Endpoint 5: Delete Video Index
# ----------------------------------------------------------------------

@search_router.delete("/video/{video_id}", status_code=status.HTTP_200_OK)
async def delete_video(
    video_id: uuid.UUID,
    db: db_dependency,
    minio: Minio = Depends(get_minio)
):
    """
    Deletes the IndexedVideo record, all associated VideoFrame rows,
    and removes both the original video and extracted clips from MinIO.
    """
    stmt = select(IndexedVideo).filter(IndexedVideo.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found.")

    # Delete all video frames from DB
    await db.execute(delete(VideoFrame).filter(VideoFrame.video_id == video_id))

    # Delete original video from MinIO
    try:
        minio.remove_object("camera-archive-videos", video.storage_path)
    except Exception as e:
        print(f"[WARN] Could not delete video from MinIO: {e}")

    # Delete all extracted clips from MinIO
    try:
        clips_prefix = f"extracted_clips/{video_id}/"
        objects = minio.list_objects("extracted-search-clips", prefix=clips_prefix, recursive=True)
        for obj in objects:
            minio.remove_object("extracted-search-clips", obj.object_name)
    except Exception as e:
        print(f"[WARN] Could not delete clips from MinIO: {e}")

    # Delete the IndexedVideo record
    await db.delete(video)
    await db.commit()

    # Revoke/Cancel the Celery task if it is currently indexing or pending
    try:
        redis_client = get_redis_client()
        task_id = redis_client.get(f"indexing:task_id:{video_id}")
        if task_id:
            from search.celery_tasks.tasks import celery_app
            celery_app.control.revoke(task_id, terminate=True)
            redis_client.delete(f"indexing:task_id:{video_id}")
            print(f"[INFO] Revoked Celery task {task_id} for video {video_id}")
    except Exception as e:
        print(f"[WARN] Failed to revoke Celery task for video {video_id}: {e}")

    return {"message": f"Video {video_id} and all associated frames/clips have been deleted."}


# ----------------------------------------------------------------------
# Endpoint 6: Start Recording from Camera (Record & Index)
# ----------------------------------------------------------------------

@search_router.post("/record/{camera_id}", status_code=status.HTTP_202_ACCEPTED)
async def start_recording(
    camera_id: uuid.UUID,
    request: RecordRequest = RecordRequest()
):
    """
    Starts recording from a camera's RTSP stream in rolling chunks.
    Each chunk is automatically uploaded to MinIO and queued for indexing.

    The recording runs as a Celery background task and can be stopped
    early via POST /api/search/record/{camera_id}/stop.
    """
    redis_client = get_redis_client()

    # Check if already recording this camera
    status_key = f"recording:status:{camera_id}"
    existing = redis_client.hgetall(status_key)
    if existing and existing.get("status") == "recording":
        raise HTTPException(
            status_code=409,
            detail=f"Camera {camera_id} is already being recorded. Stop it first."
        )

    # Dispatch the Celery background recording task
    record_and_index_task.delay(
        camera_id=str(camera_id),
        duration=request.duration,
        chunk_size=request.chunk_size,
        sampling_rate=request.sampling_rate
    )

    return {
        "camera_id": str(camera_id),
        "status": "recording",
        "duration": request.duration,
        "chunk_size": request.chunk_size,
        "message": f"Recording started. Will record {request.duration}s in {request.chunk_size}s chunks."
    }


# ----------------------------------------------------------------------
# Endpoint 7: Stop Recording
# ----------------------------------------------------------------------

@search_router.post("/record/{camera_id}/stop")
async def stop_recording(camera_id: uuid.UUID):
    """
    Sends a stop signal to an active recording task for the given camera.
    The current chunk will finish writing and uploading before the task exits.
    """
    redis_client = get_redis_client()

    redis_key = f"stop:record:{camera_id}"
    redis_client.set(redis_key, "1")

    # Clear status key immediately to unlock the camera for new recordings instantly
    status_key = f"recording:status:{camera_id}"
    redis_client.delete(status_key)

    return {
        "camera_id": str(camera_id),
        "message": "Stop signal sent. Recording will finish current chunk and stop."
    }


@search_router.get("/record/active")
async def get_active_recordings(db: db_dependency):
    """
    Returns a list of all active recording sessions across all cameras.
    """
    redis_client = get_redis_client()

    active = []
    try:
        keys = redis_client.keys("recording:status:*")
    except Exception as e:
        print(f"[ERROR] Failed to query active recordings from Redis: {e}")
        return active
    
    # Query all cameras to map camera_id -> room, building, camera_number
    cams_stmt = select(Camera).order_by(Camera.date_created.asc())
    cams_result = await db.execute(cams_stmt)
    all_cameras = cams_result.scalars().all()
    camera_map = {}
    for idx, cam in enumerate(all_cameras):
        camera_map[str(cam.id)] = {
            "room": cam.room,
            "building": cam.building,
            "number": f"Camera {idx + 1}"
        }

    for k in keys:
        try:
            data = redis_client.hgetall(k)
        except Exception as e:
            print(f"[ERROR] Failed to hgetall key {k} from Redis: {e}")
            continue
        if data and data.get("status") == "recording":
            cam_id = data.get("camera_id")
            cam_info = camera_map.get(str(cam_id), {})
            active.append({
                "camera_id": cam_id,
                "status": "recording",
                "chunks_recorded": int(data.get("chunks_recorded", 0)),
                "start_time": int(data["start_time"]) if "start_time" in data else None,
                "camera_room": cam_info.get("room"),
                "camera_building": cam_info.get("building"),
                "camera_number": cam_info.get("number")
            })
            
    return active


# ----------------------------------------------------------------------
# Endpoint 8: Check Recording Status
# ----------------------------------------------------------------------

@search_router.get("/record/{camera_id}/status", response_model=RecordingStatusResponse)
async def get_recording_status(camera_id: uuid.UUID):
    """
    Returns the current status of a recording session for a camera.
    Status is tracked in Redis and expires 1 hour after completion.
    """
    redis_client = get_redis_client()

    status_key = f"recording:status:{camera_id}"
    data = redis_client.hgetall(status_key)

    if not data:
        return RecordingStatusResponse(
            camera_id=str(camera_id),
            status="not_found"
        )

    return RecordingStatusResponse(
        camera_id=str(camera_id),
        status=data.get("status", "unknown"),
        chunks_recorded=int(data.get("chunks_recorded", 0)),
        start_time=int(data["start_time"]) if "start_time" in data else None,
        elapsed_seconds=float(data["elapsed_seconds"]) if "elapsed_seconds" in data else None,
        error=data.get("error")
    )


# Required for storage_path ext parsing
from pathlib import Path


# ----------------------------------------------------------------------
# Endpoint 9: Stream Clip Proxy — avoids CORS issues with MinIO
# ----------------------------------------------------------------------

@search_router.get("/clip/{video_id}/{frame_number}")
async def stream_clip(video_id: uuid.UUID, frame_number: int, timestamp: float = 0.0):
    """
    Proxy endpoint that streams a video clip from MinIO through FastAPI.
    This avoids browser CORS/auth issues when accessing MinIO directly.
    Returns 404 if the clip hasn't been generated yet (Celery task still running).
    """
    from fastapi.responses import StreamingResponse, Response
    import io

    minio = get_minio()
    clip_object_name = f"extracted_clips/{video_id}/clip_frame_{frame_number}_{timestamp:.2f}s.webm"

    try:
        response = minio.get_object("extracted-search-clips", clip_object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return Response(
            content=data,
            media_type="video/webm",
            headers={
                "Content-Disposition": f"inline; filename=clip_{frame_number}.webm",
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache",
            }
        )
    except Exception as e:
        err_str = str(e).lower()
        if "nosuchkey" in err_str or "no such key" in err_str or "does not exist" in err_str or "404" in err_str:
            raise HTTPException(status_code=404, detail="Clip not yet generated. Please retry shortly.")
        raise HTTPException(status_code=500, detail=f"Error fetching clip: {e}")


@search_router.get("/clip-status/{video_id}/{frame_number}")
async def get_clip_status(video_id: uuid.UUID, frame_number: int, timestamp: float = 0.0):
    """Check if a clip has been generated yet without downloading it."""
    minio = get_minio()
    clip_object_name = f"extracted_clips/{video_id}/clip_frame_{frame_number}_{timestamp:.2f}s.webm"
    try:
        minio.stat_object("extracted-search-clips", clip_object_name)
        return {"ready": True, "clip_url": f"/api/search/clip/{video_id}/{frame_number}?timestamp={timestamp:.2f}"}
    except Exception:
        return {"ready": False}


@search_router.get("/video/{video_id}/stream")
async def stream_full_video(video_id: uuid.UUID, db: db_dependency):
    """Redirects to a presigned MinIO URL to stream the full video directly to the browser."""
    from fastapi.responses import RedirectResponse
    from datetime import timedelta
    
    minio = get_minio()
    stmt = select(IndexedVideo).filter(IndexedVideo.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    try:
        url = minio.presigned_get_object(
            "camera-archive-videos", 
            video.storage_path, 
            expires=timedelta(hours=1)
        )
        return RedirectResponse(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating stream URL: {e}")


@search_router.get("/video/{video_id}/frames", response_model=List[VideoFrameResponse])
async def get_video_frames(video_id: uuid.UUID, db: db_dependency):
    """Retrieves all indexed frames and descriptions for a specific video, sorted chronologically."""
    stmt = select(IndexedVideo).filter(IndexedVideo.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    stmt_frames = select(VideoFrame).filter(VideoFrame.video_id == video_id).order_by(VideoFrame.frame_number.asc())
    result_frames = await db.execute(stmt_frames)
    frames = result_frames.scalars().all()
    
    return [
        VideoFrameResponse(
            frame_number=f.frame_number,
            timestamp_offset=f.timestamp_offset,
            description=f.description
        ) for f in frames
    ]


