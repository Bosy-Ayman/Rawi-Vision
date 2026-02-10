from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from datetime import datetime
from database import Base

class OnboardingFile(Base):
    __tablename__ = "onboarding_files"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(nullable=False)
    date_created : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())