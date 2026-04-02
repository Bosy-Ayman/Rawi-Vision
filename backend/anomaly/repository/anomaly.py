from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from ..models.anomaly import Anomaly
from ..schemas.anomaly import AnomalyCreate


class AnomalyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_new_anomaly(self, data: AnomalyCreate) -> Anomaly:
        new_anomaly = Anomaly(
            anomaly_type=data.anomaly_type,
            description=data.description,
            confidence_score=data.confidence_score,
            camera_id=data.camera_id,
            image_url=data.image_url,
            employee_id=data.employee_id,
        )
        self.db.add(new_anomaly)
        await self.db.commit()
        await self.db.refresh(new_anomaly)
        return new_anomaly

    async def fetch_anomalies(self, limit: int = 50) -> list[Anomaly]:
        result = await self.db.execute(
            select(Anomaly).order_by(desc(Anomaly.detected_at)).limit(limit)
        )
        return result.scalars().all()

    async def fetch_by_id(self, anomaly_id: int) -> Anomaly | None:
        result = await self.db.execute(
            select(Anomaly).where(Anomaly.id == anomaly_id)
        )
        return result.scalars().one_or_none()
