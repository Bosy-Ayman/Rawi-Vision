import asyncio
import os
import sys

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine

async def migrate():
    from sqlalchemy import text
    print("Starting migration...")
    async with engine.begin() as conn:
        try:
            print("Adding columns to video_appearances...")
            await conn.execute(
                text("ALTER TABLE video_appearances ADD COLUMN bbox_x1 INTEGER")
            )
        except Exception as e:
            print(f"Column bbox_x1 might exist: {e}")

        try:
            await conn.execute(
                text("ALTER TABLE video_appearances ADD COLUMN bbox_y1 INTEGER")
            )
        except Exception as e:
            pass

        try:
            await conn.execute(
                text("ALTER TABLE video_appearances ADD COLUMN bbox_x2 INTEGER")
            )
        except Exception as e:
            pass

        try:
            await conn.execute(
                text("ALTER TABLE video_appearances ADD COLUMN bbox_y2 INTEGER")
            )
        except Exception as e:
            pass

        try:
            await conn.execute(
                text("ALTER TABLE video_appearances ADD COLUMN is_identified BOOLEAN NOT NULL DEFAULT TRUE")
            )
        except Exception as e:
            pass

        try:
            print("Creating index...")
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_video_appearances_is_identified ON video_appearances(video_id, is_identified)")
            )
        except Exception as e:
            pass

        try:
            print("Dropping NOT NULL constraint on employee_id...")
            await conn.execute(
                text("ALTER TABLE video_appearances ALTER COLUMN employee_id DROP NOT NULL")
            )
        except Exception as e:
            print(f"Failed to drop constraint: {e}")
            
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
