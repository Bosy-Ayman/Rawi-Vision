import cv2
import os
import numpy as np
import logging

logger = logging.getLogger(__name__)


_FACE_NET = None
_FACE_NET_PROTO = None  

def _get_face_detector():
    global _FACE_NET
    if _FACE_NET is None:
        #lightweight fallback
        _FACE_NET = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _FACE_NET


def _blur_faces(frame: np.ndarray) -> np.ndarray:
    # Detect faces and apply a strong Gaussian blur over each bounding box.
    # Falls back gracefully if the cascade fails to load.
    try:
        detector = _get_face_detector()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        for (x, y, w, h) in faces:
            roi = frame[y : y + h, x : x + w]
            k = max(51, (w // 5) | 1)
            frame[y : y + h, x : x + w] = cv2.GaussianBlur(roi, (k, k), 0)
        return frame
    except Exception as exc:
        logger.warning(f"face blurring failed (skipping): {exc}")
        return frame


def save_frame(
    base_dir: str,
    cam_id: str,
    frame_id: int,
    frame: np.ndarray,
    stage: str = "selected_frames",
    blur_faces: bool = True,
    target_size: tuple = (640, 360),
) -> str:
     
    path = os.path.join(base_dir, cam_id, stage)
    os.makedirs(path, exist_ok=True)
    frame = cv2.resize(frame, target_size)
    if blur_faces:
        frame = _blur_faces(frame)

    file_path = os.path.join(path, f"frame_{frame_id:06d}.jpg")
    ok = cv2.imwrite(file_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        logger.error(f"failed to write frame: {file_path}")
        return ""

    return file_path
