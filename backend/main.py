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

from database import get_db
from minio import Minio
import os

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: launches the Kafka consumer as a background task.
    Shutdown: cancels it cleanly.
    """
    from anomaly.service.anomaly import AnomalyService
    from anomaly.repository.anomaly import AnomalyRepository

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
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        logger.info("Kafka consumer stopped.")


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
