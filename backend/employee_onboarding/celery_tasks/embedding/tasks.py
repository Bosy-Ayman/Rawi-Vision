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
        print("[INFO] Initializing YOLOv12m-face and InceptionResnetV1 for embeddings...")
        from ultralytics import YOLO
        from facenet_pytorch import InceptionResnetV1
        import torch
        from pathlib import Path
        
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        face_weights = backend_dir / "camera_ingestion" / "ai" / "weights" / "yolov12m-face.pt"
        
        _detector = YOLO(str(face_weights)).to(device)
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
        # Run YOLO face detector
        results = detector(image, verbose=False, conf=0.3)
        if not results or len(results[0].boxes) == 0:
            print(f"Warning: no face detected in image {idx}, skipping.")
            continue
            
        # Get the first face
        box = results[0].boxes[0]
        fx1, fy1, fx2, fy2 = map(int, box.xyxy[0])
        h, w = image.shape[:2]
        fx1, fy1 = max(0, fx1), max(0, fy1)
        fx2, fy2 = min(w, fx2), min(h, fy2)
        
        face_crop = image[fy1:fy2, fx1:fx2]
        if face_crop.size == 0:
            continue
            
        # Resize to 160x160 for InceptionResnetV1
        face_resized = cv2.resize(face_crop, (160, 160))
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        
        # Normalize
        face_norm = face_rgb.astype(np.float32) / 255.0
        face_norm = (face_norm - 0.5) / 0.5
        face_tensor = torch.tensor(np.transpose(face_norm, (2, 0, 1))).unsqueeze(0).to(device)
        face_tensor = face_tensor.to(next(embedder.parameters()).dtype)
        
        with torch.no_grad():
            embedding = embedder(face_tensor).cpu().numpy().squeeze()
            
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
