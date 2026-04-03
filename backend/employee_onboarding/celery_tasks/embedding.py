import cv2
import os
import pickle
import numpy as np
from mtcnn import MTCNN
from keras_facenet import FaceNet
from celery import Celery, shared_task
import httpx
import uuid
from ..schemas.employee import EmployeeUpdate
from ..utils.minio_storage_client import MinioStorageClient
import asyncio

BASE_URL = "http://localhost:8000"
app = Celery('tasks', broker='amqp://guest:guest@localhost:5672//') # from the celery documentation: In production you’ll want to run the worker in the background as a daemon. To do this you need to use the tools provided by your platform, or something like supervisord (see Daemonization for more information).

detector = MTCNN()
embedder = FaceNet()

def generate_embedding(images_bytes):
    embeddings = []
    processed = 0
    for idx, image_bytes in enumerate(images_bytes, 1):
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if image is None:
            print(f"Warning: could not decode image {idx}, skipping.")
            continue
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # [1] MTCNN face detection
        faces = detector.detect_faces(rgb_image)
        if not faces:
            print(f"Warning: no face detected in image {idx}, skipping.")
            continue
        x, y, w, h = faces[0]['box']
        x, y = max(0, x), max(0, y)
        x2, y2 = min(rgb_image.shape[1], x + w), min(rgb_image.shape[0], y + h)
        face_crop = rgb_image[y:y2, x:x2]
        # [2] FaceNet embedding
        embedding = embedder.embeddings([face_crop])[0]
        embeddings.append(embedding)
        processed += 1
        print(f"Processed {processed} images so far.")
    if embeddings:
        avg_embedding = np.mean(np.array(embeddings), axis=0)
        return avg_embedding
    return None

@app.task
def create_embedding_task(bucket_name, employee_id: str): #generates the embedding and puts it in the database
    try:
        object_storage = MinioStorageClient()
        images_bytes = object_storage.get_objects_binary(bucket_name=bucket_name, prefix=f"{employee_id}")
        embedding = generate_embedding(images_bytes)
        new_employee = {"embedding":embedding.tolist(), "embedding_status": "done"} # embedding is changed into a list to make the json object serializable 
        with httpx.Client() as client:
            response = client.patch(f"{BASE_URL}/employee/{employee_id}",json=new_employee,headers={"Authorization": "Bearer sherlockholmes"})  # this is for secure internal calls
        return response.status_code
    except Exception as error:
        raise error
