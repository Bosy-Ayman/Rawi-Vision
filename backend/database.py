import os
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import Config

URL_DATABASE = Config.DATABASE_URL

engine = create_async_engine(
    URL_DATABASE,
    pool_pre_ping=True,    # ← detects and discards stale connections
    pool_recycle=1800,     # ← recycle connections every 30 min
    pool_size=10,
    max_overflow=20,
)

sessionlocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db = sessionlocal()
    try:
        yield db
    finally:
        await db.close()

db_dependency = Annotated[AsyncSession, Depends(get_db)]