import cv2
import time
import logging

logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self, cameras: dict, settings: dict):
        self.cameras = cameras
        self.rtsp_retries = settings.get("rtsp_retries", 3)
        self.retry_delay = settings.get("retry_delay_sec", 2)
        self.frame_timeout = settings.get("frame_read_timeout_sec", 10)

   
    def _open_source(self, source_path: str, source_type: str = "video"):
        attempts = self.rtsp_retries if source_type == "rtsp" else 1

        for attempt in range(1, attempts + 1):
            logger.info(f"open [{attempt}/{attempts}]: {source_path}")
            cap = cv2.VideoCapture(source_path)

            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 25
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                logger.info(f" opened fps={fps:.1f}  total_frames={total}")
                return cap, fps

            logger.warning(f"Cannot open (attempt {attempt})")
            cap.release()

            if attempt < attempts:
                time.sleep(self.retry_delay * attempt) 

        logger.error(f"Failed to open after {attempts} attempts: {source_path}")
        return None, 25

  

    def stream_frames(self, cam_id: str, frame_skip: int = 1):
        
        # Generator – yields (global_frame_id, frame, source_fps) tuples.
        # Only the current frame is kept in memory at any one time

        sources = self.cameras[cam_id]["sources"]
        global_id = 0

        for src in sources:
            source_type = src.get("type", "video")
            cap, fps = self._open_source(src["path"], source_type)

            if cap is None:
                continue

            frame_index = 0
            consecutive_failures = 0
            max_consecutive_failures = 30  

            while True:
                ret, frame = cap.read()

                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            f"Stream ended or {consecutive_failures} "
                            f"consecutive read failures – stopping {src['path']}"
                        )
                        break
                   
                    if source_type == "rtsp":
                        time.sleep(0.1)
                    continue

                consecutive_failures = 0

                if frame_index % frame_skip == 0:
                    yield global_id, frame, fps
                    global_id += 1

                frame_index += 1

            cap.release()

        logger.info(f"Stream complete for {cam_id}: yielded {global_id} frames")
