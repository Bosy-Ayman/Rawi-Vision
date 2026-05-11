from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.license_store import LicenseStore, CheckInLog
import uuid

class LicenseStoreRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_installation_uuid(self, installation_uuid: uuid.UUID):
        try:
            result = await self.db.execute(select(LicenseStore).where(LicenseStore.installation_uuid == installation_uuid))
            return result.scalars().one_or_none()
        except Exception as error:
            raise error

    async def upsert_token(self, installation_uuid: uuid.UUID, token: str):
        try:
            from datetime import datetime, timezone
            existing = await self.get_by_installation_uuid(installation_uuid)
            if existing:
                existing.token = token
                existing.last_check_in_at = datetime.now(timezone.utc)
                await self.db.commit()
                await self.db.refresh(existing)
                return existing
            else:
                new_store = LicenseStore(installation_uuid=installation_uuid, token=token)
                self.db.add(new_store)
                await self.db.commit()
                await self.db.refresh(new_store)
                return new_store
        except Exception as error:
            raise error

    async def log_check_in(self, installation_uuid: uuid.UUID, status: str, message: str = None):
        try:
            log = CheckInLog(installation_uuid=installation_uuid, status=status, message=message,)
            self.db.add(log)
            await self.db.commit()
        except Exception as error:
            raise error

    async def get_check_in_logs(self, installation_uuid: uuid.UUID):
        try:
            result = await self.db.execute(select(CheckInLog).where(CheckInLog.installation_uuid == installation_uuid).order_by(CheckInLog.attempted_at.desc()))
            return result.scalars().all()
        except Exception as error:
            raise error
