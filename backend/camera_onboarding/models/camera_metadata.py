from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from database import Base
from datetime import datetime
from sqlalchemy import JSON
import uuid 

class CameraMetadata(Base):
    __tablename__ = "camera_metadata"
    
    room: Mapped[str] = mapped_column(nullable=False)
    building: Mapped[str] = mapped_column(nullable=False)
    mac_address: Mapped[str] = mapped_column(primary_key=True)
    ip_address: Mapped[str] = mapped_column(nullable=False)
    rtsp_urls:  Mapped[list[str]] = mapped_column(JSON,nullable=False)
    username: Mapped[str] = mapped_column(nullable=False)
    password:  Mapped[str] = mapped_column(nullable=False)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())