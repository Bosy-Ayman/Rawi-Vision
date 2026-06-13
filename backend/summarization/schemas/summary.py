from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime

class VideoSummaryBase(BaseModel):
    video_id: str
    camera_id: str
    generation_type: str = "manual"

class VideoSummaryCreate(VideoSummaryBase):
    pass

class VideoSummaryResponse(VideoSummaryBase):
    id: UUID4
    summary_storage_path: Optional[str] = None
    status: str
    date_created: datetime
    date_completed: Optional[datetime] = None

    class Config:
        from_attributes = True

class AutoSummarizeSettings(BaseModel):
    auto_summarize: bool
