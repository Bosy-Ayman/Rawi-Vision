from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Date, DateTime, UniqueConstraint
from database import Base
from datetime import date, datetime
from sqlalchemy.orm import Mapped, mapped_column
import uuid  
from sqlalchemy.sql import func

class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint('employee_id', 'day', name='uq_employee_day'),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    day: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
