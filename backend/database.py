import os
import socket
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# For pgvector asyncpg support
from pgvector.asyncpg import register_vector

# Load variables from .env if present
load_dotenv()

def get_working_db_url():
    """Check which database port is open and return the correct connection string."""
    try:
        with socket.create_connection(("localhost", 5433), timeout=1):
            print("Detected database on port 5433.")
            return "postgresql+asyncpg://shahd:password@localhost:5433/rawivision_db"
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass 
    
    print("Detected database on default port (5432).")
    return os.environ.get('DATABASE_URL', 'postgresql+asyncpg://shahd:password@localhost:5432/rawivision_db')

URL_DATABASE = get_working_db_url()

engine = create_async_engine(URL_DATABASE)

# Fix: Register pgvector with asyncpg so it knows how to decode vector columns!
@event.listens_for(engine.sync_engine, 'connect')
def receive_connect(dbapi_connection, connection_record):
    dbapi_connection.run_async(register_vector)

# Fix: expire_on_commit=False prevents SQLAlchemy from throwing "MissingGreenlet" 
# when accessing an object's attributes (like new_employee.id) after a commit!
sessionlocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

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