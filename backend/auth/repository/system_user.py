import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.system_user import SystemUser, SystemRole


class SystemUserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_system_user(self, email: str, full_name: str, role: SystemRole) -> SystemUser:
        new_user = SystemUser(email=email, full_name=full_name, role=role)
        self.db.add(new_user)
        # We only flush here; commit is handled by the service layer
        await self.db.flush()
        return new_user

    async def get_by_email(self, email: str) -> SystemUser | None:
        result = await self.db.execute(select(SystemUser).where(SystemUser.email == email))
        return result.scalars().one_or_none()

    async def get_by_id(self, id: uuid.UUID) -> SystemUser | None:
        result = await self.db.execute(select(SystemUser).where(SystemUser.id == id))
        return result.scalars().one_or_none()

    async def get_all(self) -> list[SystemUser]:
        result = await self.db.execute(select(SystemUser))
        return result.scalars().all()

    async def link_google_id(self, user: SystemUser, google_id: str) -> SystemUser:
        """Called on first Google login to persist the provider ID."""
        user.google_id = google_id
        await self.db.flush()
        return user

    async def delete_system_user(self, user: SystemUser) -> None:
        await self.db.delete(user)
