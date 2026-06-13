import uuid
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict, Any

class SearchQueryRequest(BaseModel):
    video_id: uuid.UUID
    query: str
    top_k: int = 10
    use_llm: bool = True

class SearchResult(BaseModel):
    frame_id: int
    timestamp: float
    similarity: float
    description: str
    clip_url: Optional[str] = None
    track_ids: List[int] = []

class SearchQueryResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResult]
    reid_tracks: Dict[str, Any] = {}
    llm_answer: Optional[str] = None

class VideoStatusResponse(BaseModel):
    video_id: uuid.UUID
    filename: str
    status: str
    sampling_rate: int
    date_created: datetime
    progress_percent: Optional[int] = 0
    frames_processed: Optional[int] = 0
    total_frames: Optional[int] = 0
    camera_room: Optional[str] = None
    camera_building: Optional[str] = None
    camera_number: Optional[str] = None



class RecordRequest(BaseModel):
    duration: int = 600       # Total recording time in seconds (default 10 min)
    chunk_size: int = 300     # Size of each chunk in seconds (default 5 min)
    sampling_rate: int = 16   # Frame sampling rate for indexing
    burn_bboxes: bool = False # Burn bounding boxes into the video chunk



class RecordingStatusResponse(BaseModel):
    camera_id: str
    status: str               # recording, completed, failed, not_found
    chunks_recorded: int = 0
    start_time: Optional[int] = None
    elapsed_seconds: Optional[float] = None
    error: Optional[str] = None


class VideoFrameResponse(BaseModel):
    frame_number: int
    timestamp_offset: float
    description: str


