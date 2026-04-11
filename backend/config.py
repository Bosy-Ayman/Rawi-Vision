import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL")
    RABBITMQ_BROKER_URL = os.getenv("BROKER_URL")
    SERVER_URL = os.getenv("SERVER_URL")
    MINIO_SERVER_URL = os.getenv("MINIO_SERVER_URL")
    RTSP_URLS = os.getenv("RTSP_URLS")
    DB_CONFIG = os.getenv("DB_CONFIG")
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = os.getenv("REDIS_PORT")
