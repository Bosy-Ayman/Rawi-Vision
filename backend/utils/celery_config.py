"""
Celery configuration with queue routing for 6GB RAM optimization
"""

from celery import Celery
from kombu import Exchange, Queue

celery_app = Celery('rawi_vision')

# RabbitMQ broker
celery_app.conf.broker_url = 'amqp://guest:guest@localhost:5672//'
celery_app.conf.result_backend = 'redis://localhost:6379/0'

# Queue definitions - separate by resource usage
celery_app.conf.task_queues = (
    Queue('indexing', Exchange('indexing'), routing_key='indexing.#', queue_arguments={'x-max-priority': 10}),
    Queue('anomaly', Exchange('anomaly'), routing_key='anomaly.#', queue_arguments={'x-max-priority': 10}),
    Queue('face_recognition', Exchange('face_recognition'), routing_key='face.#', queue_arguments={'x-max-priority': 10}),
    Queue('embedding', Exchange('embedding'), routing_key='embedding.#'),
    Queue('summarization', Exchange('summarization'), routing_key='summarization.#'),
)

# Route tasks to specific queues
celery_app.conf.task_routes = {
    'search.celery_tasks.tasks.index_video_task': {'queue': 'indexing'},
    'search.celery_tasks.tasks.record_and_index_task': {'queue': 'indexing'},
    'anomaly.celery_tasks.tasks.run_anomaly_detection': {'queue': 'anomaly'},
    'camera_ingestion.celery_tasks.face_recognition.tasks.run_face_recognition_logic': {'queue': 'face_recognition'},
    'employee_onboarding.celery_tasks.embedding.tasks.create_embedding_task': {'queue': 'embedding'},
    'summarization.celery_tasks.tasks.generate_video_summary_task': {'queue': 'summarization'},
}

# Timezone and task settings
celery_app.conf.timezone = 'UTC'
celery_app.conf.task_serializer = 'json'
celery_app.conf.accept_content = ['json']
celery_app.conf.result_serializer = 'json'
celery_app.conf.task_track_started = True
celery_app.conf.task_time_limit = 3600  # 1 hour hard limit
celery_app.conf.task_soft_time_limit = 3300  # 55 min warning

celery_app.autodiscover_tasks([
    "camera_ingestion.celery_tasks.ingestion",
    "camera_ingestion.celery_tasks.face_recognition",
    "employee_onboarding.celery_tasks.embedding.tasks",
    "anomaly.celery_tasks",
    "search.celery_tasks",
    "summarization.celery_tasks"
])
