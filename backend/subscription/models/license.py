import uuid
from datetime import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import DateTime, String
from sqlalchemy.sql import func

class LicenseInfo(Base):
    __tablename__ = "license_info"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    installation_uuid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, default="trial")  # active, suspended, expired, canceled
    tier: Mapped[str] = mapped_column(String, default="0")  # "0" (Attendance only), "1" (Search), "2" (Summarization)
    last_checked: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
