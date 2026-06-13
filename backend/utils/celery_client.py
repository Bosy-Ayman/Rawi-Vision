import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import torch
    if torch.cuda.is_available():
        print("[INFO] Initializing CUDA context early to prevent DLL load conflicts...")
        torch.cuda.init()
except Exception as e:
    print(f"[WARN] Early CUDA initialization failed: {e}")


from celery import Celery
from config import Config

celery_app = Celery(
    "rawivision",
    broker=Config.RABBITMQ_BROKER_URL
)

celery_app.autodiscover_tasks([
    "camera_ingestion.celery_tasks.ingestion",
    "camera_ingestion.celery_tasks.face_recognition",
    "employee_onboarding.celery_tasks.embedding.tasks.create_embedding_task",
    "anomaly.celery_tasks",
    "search.celery_tasks",
    "summarization.celery_tasks"
])