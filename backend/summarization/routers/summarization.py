from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import uuid

import os
from datetime import timedelta
from minio import Minio

from database import get_db
from ..models.summary import VideoSummary
from ..schemas.summary import VideoSummaryCreate, VideoSummaryResponse, AutoSummarizeSettings
from utils.celery_client import celery_app
from camera_ingestion.utils.redis import redis_client

summarization_router = APIRouter(prefix="/api/summarization", tags=["Summarization"])

def _get_minio():
    url = (
        os.getenv("MINIO_SERVER_URL", "127.0.0.1:9000")
        .replace("http://", "")
        .replace("https://", "")
    )
    return Minio(
        url,
        access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        secure=False,
    )


@summarization_router.post("/generate/{video_id}", response_model=VideoSummaryResponse)
async def generate_summary(video_id: str, camera_id: str, storage_path: str, db: AsyncSession = Depends(get_db)):
    # Check if a summary already exists
    stmt = select(VideoSummary).filter(VideoSummary.video_id == video_id)
    result = await db.execute(stmt)
    existing_summary = result.scalars().first()
    
    if existing_summary and existing_summary.status != "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Summary is already generated or in progress")

    summary_id = str(uuid.uuid4())
    
    new_summary = VideoSummary(
        id=summary_id,
        video_id=video_id,
        camera_id=camera_id,
        status="pending",
        generation_type="manual"
    )
    db.add(new_summary)
    await db.commit()
    await db.refresh(new_summary)

    celery_app.send_task(
        "summarization.tasks.generate_video_summary_task",
        args=[summary_id, video_id, camera_id, storage_path]
    )

    return new_summary

@summarization_router.get("/list", response_model=List[VideoSummaryResponse])
async def list_summaries(db: AsyncSession = Depends(get_db)):
    stmt = select(VideoSummary).order_by(VideoSummary.date_created.desc())
    result = await db.execute(stmt)
    summaries = result.scalars().all()
    return summaries

@summarization_router.post("/settings/auto")
async def update_auto_summarize_settings(settings: AutoSummarizeSettings):
    try:
        redis_client.set("auto_summarize_enabled", "true" if settings.auto_summarize else "false")
        return {"status": "success", "auto_summarize": settings.auto_summarize}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@summarization_router.get("/settings/auto")
async def get_auto_summarize_settings():
    try:
        val = redis_client.get("auto_summarize_enabled")
        return {"auto_summarize": val == "true"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@summarization_router.get("/progress/{summary_id}")
async def get_summary_progress(summary_id: str):
    """Returns live progress for a running summarization task from Redis."""
    try:
        key = f"summarization:progress:{summary_id}"
        data = redis_client.hgetall(key)
        if not data:
            return {"percent": 0, "stage": "pending"}
        return {
            "percent": int(data.get("percent", 0)),
            "stage": data.get("stage", "pending")
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@summarization_router.get("/video-url/{summary_id}")
async def get_summary_video_url(summary_id: str, db: AsyncSession = Depends(get_db)):
    """Return a short-lived pre-signed MinIO URL for the summary video."""
    stmt = select(VideoSummary).filter(VideoSummary.id == summary_id)
    result = await db.execute(stmt)
    summary = result.scalars().first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    if summary.status != "completed" or not summary.summary_storage_path:
        raise HTTPException(status_code=400, detail="Summary not ready")
    try:
        minio = _get_minio()
        url = minio.presigned_get_object(
            "camera-summaries",
            summary.summary_storage_path,
            expires=timedelta(hours=1)
        )
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@summarization_router.get("/video/{summary_id}/stream")
async def stream_summary_video(summary_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Streams the summary video from MinIO directly through FastAPI supporting Range Requests."""
    from fastapi.responses import StreamingResponse
    import re

    stmt = select(VideoSummary).filter(VideoSummary.id == summary_id)
    result = await db.execute(stmt)
    summary = result.scalars().first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    if summary.status != "completed" or not summary.summary_storage_path:
        raise HTTPException(status_code=400, detail="Summary not ready")

    try:
        minio = _get_minio()
        # 1. Get object metadata (size)
        stat = minio.stat_object("camera-summaries", summary.summary_storage_path)
        file_size = stat.size

        # 2. Parse the Range header
        range_header = request.headers.get("range")
        
        start = 0
        end = file_size - 1
        status_code = 200

        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
                status_code = 206

        # Bound check
        if start >= file_size:
            raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")
        if end >= file_size:
            end = file_size - 1

        content_length = end - start + 1

        # 3. Request only the specific byte range from MinIO
        response = minio.get_object(
            "camera-summaries",
            summary.summary_storage_path,
            offset=start,
            length=content_length
        )

        def iter_file():
            try:
                for chunk in response.stream(32 * 1024):
                    yield chunk
            finally:
                response.close()
                response.release_conn()

        headers = {
            "Content-Disposition": f"inline; filename={summary_id}_summary.mp4",
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }

        if status_code == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(content_length)

        return StreamingResponse(
            iter_file(),
            status_code=status_code,
            media_type="video/mp4",
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

