import cv2
import os
import pickle
import numpy as np
from celery import Celery, shared_task
import httpx
import uuid
from ...schemas.employee import EmployeeUpdate
from ...utils.minio_storage_client import MinioStorageClient
import asyncio
from utils.celery_client import celery_app
from config import Config

BASE_URL = Config.SERVER_URL

_detector = None
_embedder = None

def get_face_models():
    global _detector, _embedder
    if _embedder is None:
        print("[INFO] Initializing facenet-pytorch InceptionResnetV1 for embeddings...")
        from facenet_pytorch import MTCNN, InceptionResnetV1
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        _detector = MTCNN(keep_all=False, device=device)
        _embedder = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    return _detector, _embedder

def generate_embedding(images_bytes):
    detector, embedder = get_face_models()
    embeddings = []
    processed = 0
    import torch
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    
    for idx, image_bytes in enumerate(images_bytes, 1):
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if image is None:
            print(f"Warning: could not decode image {idx}, skipping.")
            continue
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # MTCNN from facenet-pytorch detects faces and returns cropped & normalized tensors
        # directly ready for InceptionResnetV1!
        face_tensor = detector(rgb_image)
        if face_tensor is None:
            print(f"Warning: no face detected in image {idx}, skipping.")
            continue
        
        with torch.no_grad():
            embedding = embedder(face_tensor.unsqueeze(0).to(device)).cpu().numpy()[0]
            
        embeddings.append(embedding)
        processed += 1
        print(f"Processed {processed} images so far.")
    if embeddings:
        avg_embedding = np.mean(np.array(embeddings), axis=0)
        return avg_embedding
    return None

@celery_app.task
def create_embedding_task(bucket_name, employee_id: str): #generates the embedding and puts it in the database
    try:
        object_storage = MinioStorageClient()
        images_bytes = object_storage.get_objects_binary(bucket_name=bucket_name, prefix=f"{employee_id}")
        embedding = generate_embedding(images_bytes)
        if embedding is not None:
            embedding = embedding.astype(float)  
            embedding_list = [float(x) for x in embedding]  
        else:
            embedding_list = None
        new_employee = {
            "embedding": embedding_list,
            "embedding_status": "done" if embedding_list else "failed"
        }
        print(type(new_employee["embedding"]))
        print(type(new_employee["embedding"][0]))
        with httpx.Client() as client:
            response = client.patch(f"{BASE_URL}/employee/{employee_id}",json=new_employee,headers={"Authorization": "Bearer sherlockholmes"})  # this is for secure internal calls
        return response.status_code
    except Exception as error:
        raise error
