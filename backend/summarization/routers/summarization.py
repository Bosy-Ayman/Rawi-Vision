from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import uuid

from database import get_db
from ..models.summary import VideoSummary
from ..schemas.summary import VideoSummaryCreate, VideoSummaryResponse, AutoSummarizeSettings
from utils.celery_client import celery_app
from camera_ingestion.utils.redis import redis_client

summarization_router = APIRouter(prefix="/api/summarization", tags=["Summarization"])

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
