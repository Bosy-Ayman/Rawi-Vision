from camera_onboarding.service.metadata import CameraMetadataService
from fastapi import WebSocket
import cv2, asyncio

class StreamService:
    def __init__(self, camera_metadata_service: CameraMetadataService):
        self.camera_metadata_service = camera_metadata_service
    
    async def stream(self, websocket:WebSocket, camera_ip):
        await websocket.accept()
        camera_metadata = await self.camera_metadata_service.get_camera_metadata_by_ip(ip=camera_ip)
        rtsp_urls = camera_metadata.rtsp_urls
        for url in rtsp_urls:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                break
        if cap is None or not cap.isOpened():
            raise RuntimeError(f"Could not open any RTSP stream from: {rtsp_urls}")
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                _, buf = cv2.imencode('.jpg', frame)
                await websocket.send_bytes(buf.tobytes())
                await asyncio.sleep(0.033)
        finally:
            cap.release()
            await websocket.close()

