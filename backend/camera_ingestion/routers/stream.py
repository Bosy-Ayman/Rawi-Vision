from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from ..service.stream import StreamService
from camera_onboarding.service.metadata import CameraMetadataService
from camera_onboarding.repository.camera_metdata import CameraMetadataRepository
from auth.dependencies import require_manager_ws

stream_router = APIRouter(prefix="/stream", tags=["Streaming"])


# ---------------------------------------------------------------------------
# Dependency providers
# ---------------------------------------------------------------------------

async def get_metadata_repository(
    db: AsyncSession = Depends(get_db),
) -> CameraMetadataRepository:
    return CameraMetadataRepository(db=db)


async def get_metadata_service(
    repo: CameraMetadataRepository = Depends(get_metadata_repository),
) -> CameraMetadataService:
    return CameraMetadataService(repository=repo)


async def get_stream_service(
    metadata_service: CameraMetadataService = Depends(get_metadata_service),
) -> StreamService:
    return StreamService(camera_metadata_service=metadata_service)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@stream_router.websocket("/{mac_address}")
async def start_stream(
    websocket: WebSocket,
    mac_address: str,
    token_payload: dict = Depends(require_manager_ws),
    service: StreamService = Depends(get_stream_service),
) -> None:
    try:
        await service.stream(websocket=websocket, mac_address=mac_address)

    except WebSocketDisconnect:
        # Normal client-initiated close — not an error
        print(f"[stream] Client disconnected: {mac_address}")

    except Exception as e:
        # Filter out the websockets AssertionError noise that is a known
        # library bug triggered after an OOM — it carries no actionable info.
        error_type = type(e).__name__
        if error_type not in ("AssertionError",):
            print(f"[stream] Unexpected error for {mac_address} ({error_type}): {e}")