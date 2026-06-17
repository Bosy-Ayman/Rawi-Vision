"""
Debug script to check if anomalies are in the database
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def check_database():
    from database import sessionlocal, engine, Base
    from anomaly.models.anomaly import Anomaly
    from sqlalchemy import select

    print("\n" + "="*60)
    print("CHECKING ANOMALY DATABASE")
    print("="*60)

    try:
        # Ensure tables exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[+] Database tables initialized")

        # Check for anomalies
        async with sessionlocal() as db:
            result = await db.execute(select(Anomaly).order_by(Anomaly.detected_at.desc()).limit(10))
            anomalies = result.scalars().all()

            if not anomalies:
                print("\n[-] NO ANOMALIES in database!")
                print("   This means the Kafka consumer hasn't saved any yet.")
            else:
                print(f"\n[+] Found {len(anomalies)} anomalies in database:")
                for anom in anomalies:
                    print(f"   - {anom.id}: {anom.anomaly_type} @ {anom.camera_id} ({anom.detected_at})")
                    print(f"     Description: {anom.description[:60]}...")
                    print(f"     Image URL: {anom.image_url}")
                    print()

        # Count total anomalies
        async with sessionlocal() as db:
            result = await db.execute(select(Anomaly))
            total = len(result.scalars().all())
            print(f"\nTotal anomalies in database: {total}")

    except Exception as e:
        print(f"\n[-] Database check failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())
