import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from celery import Celery

celery_app = Celery(
    "rawivision",
    broker="amqp://guest:guest@localhost:5672//"
)

celery_app.autodiscover_tasks([
    "camera_ingestion.celery_tasks.ingestion",
    "camera_ingestion.celery_tasks.face_recognition",
])