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
from camera_onboarding.service.metadata import CameraMetadataService
from camera_ingestion.utils.redis import redis_client
from ..celery_tasks.tasks import run_anomaly_detection
from uuid import uuid4

logger = logging.getLogger(__name__)

KAFKA_BROKER = "localhost:29092"
KAFKA_TOPIC = "anomaly-incidents"
MINIO_BUCKET = "anomaly-incidents"

# In-memory set of connected WebSocket clients for broadcasting
connected_clients: List[WebSocket] = []


class AnomalyService:
    def __init__(self, repository: AnomalyRepository, minio_client: Minio, metadata_service: CameraMetadataService = None):
        self.repository = repository
        self.minio = minio_client
        self.metadata_service = metadata_service

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

        try:
            from observability.metrics import ANOMALY_DETECTED_COUNTER
            ANOMALY_DETECTED_COUNTER.labels(camera_id=saved.camera_id, type=saved.anomaly_type).inc()
        except ImportError:
            pass

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

    async def start_anomaly_detection(self):
        """
        Triggers the anomaly detection Celery task for all online cameras.
        """
        if not self.metadata_service:
            raise RuntimeError("Metadata service not initialized in AnomalyService")
            
        cameras = await self.metadata_service.get_all_camera_metadata()
        if not cameras:
            return {"status": "error", "message": "No cameras found"}
            
        task_ids = []
        for camera in cameras:
            if not camera.rtsp_urls:
                continue
                
            task_id = str(uuid4())
            # We use the first working RTSP URL
            rtsp_url = camera.rtsp_urls[0]
            
            # Trigger Celery Task
            run_anomaly_detection.delay(rtsp_url, camera.mac_address, task_id)
            task_ids.append(task_id)
            
        # Store task IDs in Redis so we can stop them later
        redis_client.set('anomaly_task_ids', json.dumps(task_ids))
        return {"status": "started", "count": len(task_ids)}

    def stop_anomaly_detection(self):
        """
        Sends a stop signal to all running anomaly detection tasks via Redis.
        """
        task_ids_json = redis_client.get("anomaly_task_ids")
        if not task_ids_json:
            return {"status": "error", "message": "No active tasks found"}
            
        task_ids = json.loads(task_ids_json)
        for task_id in task_ids:
            redis_client.set(f"stop_anomaly:{task_id}", 1)
            
        return {"status": "stopped", "count": len(task_ids)}

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
