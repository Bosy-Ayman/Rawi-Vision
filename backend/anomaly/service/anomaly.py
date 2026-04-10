import io
import json
import base64
import logging
from typing import List
from fastapi import WebSocket
from aiokafka import AIOKafkaConsumer
from minio import Minio
from minio.error import S3Error
from datetime import datetime

from ..repository.anomaly import AnomalyRepository
from ..schemas.anomaly import AnomalyCreate, AnomalyTypeEnum

logger = logging.getLogger(__name__)

KAFKA_BROKER = "localhost:29092"
KAFKA_TOPIC = "anomaly-incidents"
MINIO_BUCKET = "anomaly-incidents"

# In-memory set of connected WebSocket clients for broadcasting
connected_clients: List[WebSocket] = []


class AnomalyService:
    def __init__(self, repository: AnomalyRepository, minio_client: Minio):
        self.repository = repository
        self.minio = minio_client

    async def handle_ai_event(self, event_payload: dict) -> None:
        """
        Main orchestrator called per Kafka message:
        1. Decode base64 image and upload to MinIO.
        2. Save anomaly record to PostgreSQL.
        3. Broadcast the new record to all WebSocket clients.
        """
        image_url = None

        # 1. Upload evidence frame to MinIO if present
        image_b64 = event_payload.get("image_b64")
        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
                object_name = f"anomaly_{timestamp_str}.jpg"

                self._ensure_bucket_exists()

                self.minio.put_object(
                    MINIO_BUCKET,
                    object_name,
                    io.BytesIO(image_bytes),
                    length=len(image_bytes),
                    content_type="image/jpeg",
                )
                image_url = f"http://localhost:9000/{MINIO_BUCKET}/{object_name}"
                logger.info(f"Uploaded evidence frame: {image_url}")
            except Exception as e:
                logger.error(f"MinIO upload failed: {e}")

        # 2. Save to PostgreSQL
        anomaly_data = AnomalyCreate(
            anomaly_type=AnomalyTypeEnum(event_payload.get("anomaly_type", "unknown")),
            description=event_payload.get("description", ""),
            confidence_score=float(event_payload.get("confidence_score", 0.0)),
            camera_id=event_payload.get("camera_id", "default"),
            image_url=image_url,
            employee_id=None,  # Will be filled by face recognition module
        )
        saved = await self.repository.save_new_anomaly(anomaly_data)
        logger.info(f"Saved anomaly #{saved.id}: {saved.anomaly_type}")

        # 3. Broadcast to all connected WebSocket clients
        from ..schemas.anomaly import AnomalyResponse
        response = AnomalyResponse.model_validate(saved)
        message = response.model_dump_json()
        dead_clients = []
        for ws in connected_clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            connected_clients.remove(ws)

    def _ensure_bucket_exists(self):
        try:
            if not self.minio.bucket_exists(MINIO_BUCKET):
                self.minio.make_bucket(MINIO_BUCKET)
            
            # Make bucket public so frontend can display the images
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{MINIO_BUCKET}/*"],
                    }
                ],
            }
            self.minio.set_bucket_policy(MINIO_BUCKET, json.dumps(policy))
        except S3Error as e:
            logger.error(f"MinIO bucket error: {e}")

    async def run_event_consumer(self) -> None:
        """
        Long-running background coroutine.
        Continuously listens to the Kafka topic and calls handle_ai_event per message.
        Started once on app startup via FastAPI lifespan.
        """
        consumer = AIOKafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            group_id="anomaly-backend-group",
            auto_offset_reset="latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await consumer.start()
        logger.info(f"Kafka consumer started on topic: {KAFKA_TOPIC}")
        try:
            async for message in consumer:
                try:
                    await self.handle_ai_event(message.value)
                except Exception as e:
                    logger.error(f"Error handling Kafka message: {e}")
        finally:
            await consumer.stop()
