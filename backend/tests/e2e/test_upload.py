import pytest
import os
from fastapi.testclient import TestClient
from main import app
import uuid

client = TestClient(app)

def test_upload_flow_happy_path():
    """
    Test Flow 2: E2E Video Upload & Semantic Search
    Goal: Prove that a user can upload a video, it hits MinIO, and queues a Celery task.
    """
    # 1. POST a mock video file to /api/search/upload
    fake_video_content = b"fake mp4 content"
    camera_id = str(uuid.uuid4())
    
    response = client.post(
        "/api/search/upload",
        data={
            "camera_id": camera_id,
            "sampling_rate": 16,
            "enable_face_recognition": True
        },
        files={
            "file": ("test_video.mp4", fake_video_content, "video/mp4")
        }
    )
    
    # Verify accepted
    assert response.status_code == 202
    data = response.json()
    assert "video_id" in data
    assert data["status"] == "pending"
    
    video_id = data["video_id"]
    
    # 2. Verify status endpoint reads it from DB
    status_response = client.get(f"/api/search/status/{video_id}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] == "pending"
    assert status_data["filename"] == "test_video.mp4"
    
    # 3. Verify Celery task ID is in Redis
    import redis
    r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)), db=0)
    task_id = r.get(f"indexing:task_id:{video_id}")
    assert task_id is not None
    
    # Cleanup: delete the video
    del_response = client.delete(f"/api/search/video/{video_id}")
    assert del_response.status_code == 200

def test_upload_flow_failure_case():
    """
    Test Flow 2: Failure Case
    Attempt to upload a text file masked as a video.
    """
    camera_id = str(uuid.uuid4())
    fake_txt_content = b"this is a text file, not a video"
    
    response = client.post(
        "/api/search/upload",
        data={
            "camera_id": camera_id,
            "sampling_rate": 16,
            "enable_face_recognition": True
        },
        files={
            "file": ("malicious.exe", fake_txt_content, "text/plain")
        }
    )
    
    # The API should reject non-video content types
    assert response.status_code == 400
    assert "video" in response.json()["detail"].lower()
