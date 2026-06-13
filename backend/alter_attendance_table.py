import asyncio
import asyncpg

async def run():
    try:
        conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5433/rawivision_db")
        await conn.execute("ALTER TABLE attendance ADD COLUMN look_count INTEGER DEFAULT 1;")
        await conn.close()
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(run())
