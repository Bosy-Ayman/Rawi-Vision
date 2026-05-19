import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from employee_onboarding.routers.employees import employee_router
from employee_onboarding.routers.employee_images import employee_image_router
from camera_onboarding.routers.camera import camera_router
from auth.routers.auth import auth_router
from anomaly.routers.anomaly import anomaly_router
from camera_onboarding.routers.discovery import camera_discovery_router
from camera_ingestion.routers.ingestion import ingestion_router
from camera_ingestion.routers.stream import stream_router
from attendance.routers.attendance import attendance_router
from subscription.routers.subscription import subscription_router

from database import get_db
from minio import Minio
import os

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: launches the Kafka consumer as a background task 
             and the RabbitMQ attendance consumer as a background thread.
    Shutdown: cancels them cleanly.
    """
    async for _ in get_db():
        break

    import threading
    from kombu import Connection
    from attendance.service.kombu_consumer import AttendanceConsumer
    from config import Config
    from anomaly.service.anomaly import AnomalyService
    from anomaly.repository.anomaly import AnomalyRepository

    # ── Database Migration for Profile Image URL ──────────────────────────────
    async def migrate_db():
        from database import engine
        from sqlalchemy import text
        from minio import Minio
        import os

        try:
            # 1. Add column if it doesn't exist
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE employees ADD COLUMN IF NOT EXISTS profile_image_url VARCHAR;"))
                print("[Lifespan] Successfully ensured profile_image_url column exists.")

            # 2. Ensure Minio Bucket is Public
            try:
                minio_endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
                minio_client = Minio(
                    minio_endpoint,
                    access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
                    secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
                    secure=False,
                )
                bucket_name = "employee-pictures"
                
                if minio_client.bucket_exists(bucket_name):
                    import json
                    policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": "*"},
                                "Action": ["s3:GetObject"],
                                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                            }
                        ]
                    }
                    minio_client.set_bucket_policy(bucket_name, json.dumps(policy))
                    print(f"[Lifespan] Verified public read policy on '{bucket_name}' bucket.")
            except Exception as p_err:
                print(f"[Lifespan] Could not set bucket policy: {p_err}")

            # 3. Backfill URLs for existing employees
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT id FROM employees WHERE profile_image_url IS NULL"))
                employees_without_url = result.fetchall()

                if employees_without_url:
                    print(f"[Lifespan] Found {len(employees_without_url)} employees without image URL. Attempting to fill...")
                    
                    if minio_client.bucket_exists(bucket_name):
                        updated_count = 0
                        for emp_row in employees_without_url:
                            emp_id_str = str(emp_row[0])
                            # Find their pictures in Minio
                            objects = list(minio_client.list_objects(bucket_name, prefix=f"{emp_id_str}/", recursive=True))
                            
                            if objects:
                                first_obj = objects[0]
                                # Create the public URL
                                image_url = f"http://127.0.0.1:9000/{bucket_name}/{first_obj.object_name}"
                                
                                # Update DB
                                await conn.execute(
                                    text("UPDATE employees SET profile_image_url = :url WHERE id = :id"),
                                    {"url": image_url, "id": emp_row[0]}
                                )
                                updated_count += 1
                                
                        print(f"[Lifespan] Successfully backfilled URLs for {updated_count} employees.")
                        
        except Exception as e:
            print(f"[Lifespan] Migration failed: {e}")

    await migrate_db()

    # ── Kafka / anomaly consumer ────────────────────────────────────────────
    async def start_kafka_consumer():
        async for db in get_db():
            repo = AnomalyRepository(db)
            minio_client = Minio(
                os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
                secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
                secure=False,
            )
            service = AnomalyService(repository=repo, minio_client=minio_client)
            await service.run_event_consumer()

    consumer_task = asyncio.create_task(start_kafka_consumer())
    logger.info("Kafka consumer background task started.")

    # ── RabbitMQ / attendance consumer ─────────────────────────────────────
    main_loop = asyncio.get_running_loop()
    def run_attendance_consumer(loop):
        print("[Lifespan] Starting attendance consumer thread...")
        try:
            with Connection(Config.RABBITMQ_BROKER_URL) as conn:
                print(f"[Lifespan] Connecting to broker: {Config.RABBITMQ_BROKER_URL}")
                consumer = AttendanceConsumer(connection=conn)
                # Pass the loop to the consumer so it can schedule tasks
                consumer.loop = loop
                print("[Lifespan] RabbitMQ attendance consumer is now running.")
                consumer.run()
        except Exception as exc:
            print(f"[Lifespan] RabbitMQ attendance consumer crashed: {exc}")
            logger.error(f"RabbitMQ attendance consumer crashed: {exc}")

    attendance_thread = threading.Thread(target=run_attendance_consumer, args=(main_loop,), daemon=True, name="attendance-consumer")
    attendance_thread.start()
    print("[Lifespan] Attendance consumer thread has been spawned with main loop access.")

    yield
    # ── Shutdown ────────────────────────────────────────────────────────────
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        logger.info("Kafka consumer stopped.")
    logger.info("Attendance consumer thread will stop on process exit.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employee_router)
app.include_router(employee_image_router)
app.include_router(auth_router)
app.include_router(anomaly_router)
app.include_router(camera_router)
app.include_router(camera_discovery_router)
app.include_router(ingestion_router)
app.include_router(stream_router)
app.include_router(attendance_router)
app.include_router(subscription_router)