from camera_onboarding.service.metadata import CameraMetadataService
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
import cv2, asyncio
import logging

logger = logging.getLogger(__name__)


async def _safe_close(websocket: WebSocket) -> None:
    """Close a WebSocket, ignoring errors if it's already closed."""
    try:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
    except Exception:
        pass


class StreamService:
    def __init__(self, camera_metadata_service: CameraMetadataService):
        self.camera_metadata_service = camera_metadata_service

    async def stream(self, websocket: WebSocket, camera_ip):
        await websocket.accept()
        # The frontend often passes the MAC address instead of the IP address in the URL parameter.
        # Try finding the metadata by IP first, then by MAC address.
        camera_metadata = await self.camera_metadata_service.get_camera_metadata_by_ip(ip=camera_ip)
        if camera_metadata is None:
            camera_metadata = await self.camera_metadata_service.get_camera_metadata_by_mac_address(mac_address=camera_ip)

        if camera_metadata is None:
            await websocket.send_text(f"No camera found with IP or MAC: {camera_ip}")
            await _safe_close(websocket)
            return
        rtsp_urls = camera_metadata.rtsp_urls
        if not rtsp_urls:
            await websocket.send_text(f"Camera {camera_ip} has no RTSP URLs configured")
            await _safe_close(websocket)
            return
        cap = None
        for url in rtsp_urls:
            cap = await asyncio.get_event_loop().run_in_executor(None, cv2.VideoCapture, url)
            if cap.isOpened():
                break
        if cap is None or not cap.isOpened():
            await _safe_close(websocket)
            raise RuntimeError(f"Could not open any RTSP stream from: {rtsp_urls}")
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                _, buf = cv2.imencode('.jpg', frame)
                try:
                    await websocket.send_bytes(buf.tobytes())
                except (WebSocketDisconnect, RuntimeError):
                    # Client disconnected – stop streaming gracefully
                    logger.info("Stream client disconnected for camera %s", camera_ip)
                    break
                await asyncio.sleep(0.033)
        finally:
            cap.release()
            await _safe_close(websocket)


