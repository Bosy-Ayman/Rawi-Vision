from database import Base
from sqlalchemy.orm import Mapped, mapped_column

class Plans(Base):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(primary_key=True)
    tier: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    annual_pricing: Mapped[int] = mapped_column(nullable=False)
    monthly_pricing: Mapped[int] = mapped_column(nullable=False)

