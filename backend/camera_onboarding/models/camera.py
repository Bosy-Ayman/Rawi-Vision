import uuid 
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from database import Base
from datetime import datetime

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room: Mapped[str] = mapped_column(nullable=False)
    building: Mapped[str] = mapped_column(nullable=False)
    mac_address: Mapped[str] = mapped_column(nullable=False)
    username: Mapped[str] = mapped_column(nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

