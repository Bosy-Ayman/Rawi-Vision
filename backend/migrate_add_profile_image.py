import asyncio
from sqlalchemy import text
from database import engine

async def add_profile_image_column():
    async with engine.begin() as conn:
        try:
            # Check if column already exists
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'system_users'
                    AND column_name = 'profile_image_url'
                )
            """))
            column_exists = result.scalar()

            if column_exists:
                print("✅ Column 'profile_image_url' already exists in system_users table")
            else:
                # Add the column
                await conn.execute(text("""
                    ALTER TABLE system_users
                    ADD COLUMN profile_image_url VARCHAR NULL
                """))
                print("✅ Successfully added 'profile_image_url' column to system_users table")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(add_profile_image_column())
