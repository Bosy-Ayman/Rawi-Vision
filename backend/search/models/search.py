import uuid
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
from datetime import datetime
from database import Base

class IndexedVideo(Base):
    __tablename__ = "indexed_videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    storage_path: Mapped[str] = mapped_column(nullable=False)  # MinIO object key (e.g. camera-archive-videos/uuid.mp4)
    filename: Mapped[str] = mapped_column(nullable=False)      # Original name of the uploaded video
    status: Mapped[str] = mapped_column(nullable=False, default="pending")  # pending, indexing, completed, failed
    sampling_rate: Mapped[int] = mapped_column(nullable=False, default=16)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class VideoFrame(Base):
    __tablename__ = "video_frames"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # References IndexedVideo.id
    frame_number: Mapped[int] = mapped_column(nullable=False)
    timestamp_offset: Mapped[float] = mapped_column(nullable=False)                  # Offset in seconds
    description: Mapped[str] = mapped_column(nullable=False)                          # Fused description string
    tracks: Mapped[str | None] = mapped_column(nullable=True)                         # Comma-separated track IDs
    embedding: Mapped[list[float]] = mapped_column(Vector(1152), nullable=False)      # 1152-dim pgvector column
    face_detections: Mapped[str | None] = mapped_column(nullable=True)               # JSON: [{"emp_id", "name", "confidence", "x1", "y1", "x2", "y2"}]
