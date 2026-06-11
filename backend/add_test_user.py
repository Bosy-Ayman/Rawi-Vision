import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from auth.models.system_user import SystemUser, SystemRole
from database import Base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/rawivision_db")

async def add_test_user():
    """Add a test user to the database for testing"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        # Check if test user already exists
        from sqlalchemy import select
        stmt = select(SystemUser).where(SystemUser.email == "test@example.com")
        result = await session.execute(stmt)
        existing_user = result.scalars().first()
        
        if existing_user:
            print(f"✓ Test user already exists: {existing_user.email}")
        else:
            # Create test user
            test_user = SystemUser(
                id=uuid.uuid4(),
                email="test@example.com",
                full_name="Test User",
                role=SystemRole.HR,
                google_id=None
            )
            session.add(test_user)
            await session.commit()
            print(f"✓ Test user created: {test_user.email}")
        
        # Also add an HR user
        stmt = select(SystemUser).where(SystemUser.email == "hr@rawivision.com")
        result = await session.execute(stmt)
        hr_user = result.scalars().first()
        
        if not hr_user:
            hr_user = SystemUser(
                id=uuid.uuid4(),
                email="hr@rawivision.com",
                full_name="HR Admin",
                role=SystemRole.HR,
                google_id=None
            )
            session.add(hr_user)
            await session.commit()
            print(f"✓ HR user created: {hr_user.email}")
        else:
            print(f"✓ HR user already exists: {hr_user.email}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(add_test_user())
