from sqlalchemy import ForeignKey
import uuid
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector 
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from datetime import datetime
from database import Base

class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4())
    first_name: Mapped[str] = mapped_column(nullable=False)
    last_name: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False) #should be changed later to enum or something, in order to choose between predefined roles
    embedding: Mapped[list[float] | None] = mapped_column(Vector(512), nullable=True) # bosy told me each embedding should be 512 d
    date_created : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class OnboardingFile(Base):
    __tablename__ = "onboarding_files"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(nullable=False)
    date_created : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
