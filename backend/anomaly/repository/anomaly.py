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

    async def delete_by_id(self, anomaly_id: int) -> bool:
        anomaly = await self.fetch_by_id(anomaly_id)
        if not anomaly:
            return False
        await self.db.delete(anomaly)
        await self.db.commit()
        return True

    async def delete_multiple(self, anomaly_ids: list[int]) -> int:
        from sqlalchemy import delete
        result = await self.db.execute(delete(Anomaly).where(Anomaly.id.in_(anomaly_ids)))
        await self.db.commit()
        return result.rowcount

    async def delete_all(self) -> int:
        from sqlalchemy import delete
        result = await self.db.execute(delete(Anomaly))
        await self.db.commit()
        return result.rowcount
