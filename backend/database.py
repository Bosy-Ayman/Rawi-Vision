from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# the username:password@localhost:5432/databaseName
URL_DATABASE = 'postgresql+asyncpg://shahd:password@localhost/rawivision_db' 
engine = create_async_engine(URL_DATABASE)
sessionlocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass 

async def get_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) # suitable only for development, MUST be replaced later with alembic for production and CI/CD pipelines
    db = sessionlocal()
    try:
        yield db
    finally:
        await db.close() 

db_dependency = Annotated[AsyncSession, Depends(get_db)]