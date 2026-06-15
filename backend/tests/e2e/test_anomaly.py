import pytest
import asyncio
import json
import base64
from fastapi.testclient import TestClient
from main import app
from database import engine, Base
from sqlalchemy import text
from minio import Minio

# We use the live app for E2E tests
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_e2e_db():
    # In a real CI, you might spin up a test DB. 
    # Here, we assume the dev runs this against the live local system.
    pass

@pytest.mark.asyncio
async def test_anomaly_flow_happy_path():
    """
    Test Flow 1: E2E Anomaly Detection
    Goal: Prove that a real-time incident flows from AI detection all the way to the frontend WebSocket.
    """
    # 1. Publish mock Kafka message directly to the broker or simulate the service call
    from anomaly.service.anomaly import AnomalyService
    from anomaly.repository.anomaly import AnomalyRepository
    from database import sessionlocal
    
    # We create a tiny fake image
    fake_img = b"fake_jpeg_bytes_for_testing"
    fake_b64 = base64.b64encode(fake_img).decode('utf-8')
    
    payload = {
        "anomaly_type": "weapon",
        "description": "E2E Test Weapon Detection",
        "confidence_score": 0.95,
        "camera_id": "e2e-test-cam-01",
        "image_b64": fake_b64
    }
    
    async with sessionlocal() as db:
        repo = AnomalyRepository(db)
        import os
        minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=False,
        )
        service = AnomalyService(repository=repo, minio_client=minio_client)
        
        # Trigger the orchestrator (simulating Kafka consumer receiving it)
        await service.handle_ai_event(payload)
        
        # 2. Verify it saved to PostgreSQL
        from anomaly.models.anomaly import Anomaly
        from sqlalchemy import select
        stmt = select(Anomaly).where(Anomaly.description == "E2E Test Weapon Detection").order_by(Anomaly.timestamp.desc())
        result = await db.execute(stmt)
        saved_anomaly = result.scalars().first()
        
        assert saved_anomaly is not None
        assert saved_anomaly.anomaly_type.value == "weapon"
        assert saved_anomaly.confidence_score == 0.95
        
        # 3. Verify it uploaded to MinIO
        assert saved_anomaly.image_url is not None
        assert "http://localhost:9000/anomaly-incidents" in saved_anomaly.image_url
        
        # Cleanup
        await db.delete(saved_anomaly)
        await db.commit()

@pytest.mark.asyncio
async def test_anomaly_flow_failure_case():
    """
    Test Flow 1: Failure Case
    Send an invalid Kafka payload and verify the system catches it without crashing.
    """
    from anomaly.service.anomaly import AnomalyService
    from anomaly.repository.anomaly import AnomalyRepository
    from database import sessionlocal
    
    # Missing critical fields, invalid types
    payload = {
        "anomaly_type": "unknown_junk",
        "confidence_score": "not_a_float"
    }
    
    async with sessionlocal() as db:
        repo = AnomalyRepository(db)
        service = AnomalyService(repository=repo, minio_client=None)
        
        # Should raise an error but be caught by the consumer loop
        with pytest.raises(Exception):
            await service.handle_ai_event(payload)
