from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import DateTime, String
from database import Base
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
import uuid  
from sqlalchemy.sql import func

class VideoSummary(Base):
    __tablename__ = "video_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    camera_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    summary_storage_path: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, completed, failed
    generation_type: Mapped[str] = mapped_column(String, default="manual")  # auto, manual
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    date_completed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

