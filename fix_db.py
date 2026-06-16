import asyncio
import os
import sys

# Add the current directory to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from backend.database import engine

async def fix():
    from sqlalchemy import text
    print("Fixing db...")
    async with engine.begin() as conn:
        try:
            print("Dropping NOT NULL constraint on employee_id...")
            await conn.execute(
                text("ALTER TABLE video_appearances ALTER COLUMN employee_id DROP NOT NULL")
            )
            print("Successfully dropped constraint.")
        except Exception as e:
            print(f"Failed to drop constraint: {e}")
            
if __name__ == "__main__":
    asyncio.run(fix())
