# backend/create_contact_table.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine
from database import Base
from contact.models import ContactMessage  # ensures table is known
from config import Config

async def main():
    engine = create_async_engine(Config.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Table 'contact_messages' created (or already exists).")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())