from minio import Minio
import os
from dotenv import load_dotenv
from config import Config

def minio_client_init():
    load_dotenv()
    url = Config.MINIO_SERVER_URL.replace("http://", "").replace("https://", "")
    client = Minio(url, access_key=os.getenv("MINIO_ROOT_USER"), secret_key= os.getenv("MINIO_ROOT_PASSWORD"), secure=False)
    return client