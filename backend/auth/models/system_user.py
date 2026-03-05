import uuid
import enum
from datetime import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SAEnum, DateTime, String
from sqlalchemy.sql import func


class SystemRole(str, enum.Enum):
    HR = "HR"
    MANAGER = "Manager"


class SystemUser(Base):
    __tablename__ = "system_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[SystemRole] = mapped_column(SAEnum(SystemRole, name="systemrole"), nullable=False)
    google_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
