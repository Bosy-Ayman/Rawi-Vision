import os
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from minio import Minio

from database import get_db
from auth.dependencies import require_manager
from auth.models.system_user import SystemUser
from auth.service.auth import JWT_SECRET, JWT_ALGORITHM

from ..repository.anomaly import AnomalyRepository
from ..service.anomaly import AnomalyService, connected_clients
from ..schemas.anomaly import AnomalyResponse
from camera_onboarding.service.metadata import CameraMetadataService
from camera_onboarding.repository.camera_metdata import CameraMetadataRepository

anomaly_router = APIRouter(prefix="/anomalies", tags=["anomalies"])

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")


def get_minio_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


async def get_metadata_repository(db: AsyncSession=Depends(get_db)):
    return CameraMetadataRepository(db=db)

async def get_metadata_service(repo: CameraMetadataRepository=Depends(get_metadata_repository)):
    return CameraMetadataService(repository=repo)

async def get_anomaly_service(db: AsyncSession = Depends(get_db), metadata_service: CameraMetadataService = Depends(get_metadata_service)) -> AnomalyService:
    repo = AnomalyRepository(db)
    minio = get_minio_client()
    return AnomalyService(repository=repo, minio_client=minio, metadata_service=metadata_service)


@anomaly_router.get("/", response_model=list[AnomalyResponse])
async def list_anomalies(
    service: AnomalyService = Depends(get_anomaly_service),
    current_user: SystemUser = Depends(require_manager),
):
    """Returns the 50 most recent anomalies. Requires Manager or HR role."""
    return await service.repository.fetch_anomalies()


@anomaly_router.get("/start", status_code=status.HTTP_200_OK)
async def start_anomaly_detection(
    service: AnomalyService = Depends(get_anomaly_service),
    current_user: SystemUser = Depends(require_manager),
):
    """Starts the anomaly detection pipeline for all online cameras."""
    return await service.start_anomaly_detection()


@anomaly_router.get("/stop", status_code=status.HTTP_200_OK)
async def stop_anomaly_detection(
    service: AnomalyService = Depends(get_anomaly_service),
    current_user: SystemUser = Depends(require_manager),
):
    """Stops the anomaly detection pipeline."""
    return service.stop_anomaly_detection()


@anomaly_router.delete("/remove-anomaly/{anomaly_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_anomaly(
    anomaly_id: int,
    service: AnomalyService = Depends(get_anomaly_service),
    current_user: SystemUser = Depends(require_manager),
):
    """Deletes an anomaly by ID. Requires Manager or HR role."""
    success = await service.repository.delete_by_id(anomaly_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

from pydantic import BaseModel
class BulkDeleteRequest(BaseModel):
    ids: list[int]

@anomaly_router.post("/bulk-remove", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_anomalies(
    request: BulkDeleteRequest,
    service: AnomalyService = Depends(get_anomaly_service),
    current_user: SystemUser = Depends(require_manager),
):
    """Deletes multiple anomalies by IDs."""
    await service.repository.delete_multiple(request.ids)

@anomaly_router.delete("/remove-all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_anomalies(
    service: AnomalyService = Depends(get_anomaly_service),
    current_user: SystemUser = Depends(require_manager),
):
    """Deletes all anomalies."""
    await service.repository.delete_all()

@anomaly_router.get("/{anomaly_id}", response_model=AnomalyResponse)
async def get_anomaly(
    anomaly_id: int,
    service: AnomalyService = Depends(get_anomaly_service),
    current_user: SystemUser = Depends(require_manager),
):
    """Returns a single anomaly by ID. Requires Manager or HR role."""
    anomaly = await service.repository.fetch_by_id(anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")
    return anomaly


@anomaly_router.websocket("/ws/live")
async def stream_live_alerts(
    websocket: WebSocket,
    token: str,  # Passed as query param: ws://localhost:8000/anomalies/ws/live?token=ey...
):
    """
    WebSocket endpoint for real-time anomaly alerts.
    Token is validated manually since WebSockets don't support HTTP auth headers.
    """
    # Manually verify the JWT from query param
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("email")
        role = payload.get("role")
        if not email or role not in ["HR", "Manager"]:
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    connected_clients.append(websocket)
    try:
        # Keep connection alive, client is passive receiver
        while True:
            await asyncio.sleep(30)
            await websocket.send_text('{"type": "ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
