from minio import Minio
import os
from dotenv import load_dotenv

def minio_client_init():
    load_dotenv()
    client = Minio("localhost:9000", access_key=os.getenv("MINIO_ROOT_USER"), secret_key= os.getenv("MINIO_ROOT_PASSWORD"), secure=False)
    return client