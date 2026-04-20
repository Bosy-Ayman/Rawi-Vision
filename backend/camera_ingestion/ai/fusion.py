import csv
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO
from boxmot import StrongSort # find the version of the library tha has this, do not replace this library name please (bosy,abdelrahman)
from facenet_pytorch import InceptionResnetV1
from .embedding_manager import EmbeddingManager


THRESHOLD = 1.0
FACE_RETRY_FRAMES = 10
PERSON_SKIP = 2

LOG_FILE = "events.csv"

device = "cuda:0" if torch.cuda.is_available() else "cpu"


# ── Logger ───────────────────────────────────────────────────────────────────

class EventLogger:
    """Thread-safe CSV event logger."""

    COLUMNS = ["timestamp", "event", "track_id", "name", "distance", "detail"]

    def __init__(self, path: str = LOG_FILE):
        self.path = path
        self._lock = threading.Lock()
        # Write header if file doesn't exist yet
        if not Path(path).exists():
            with open(path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=self.COLUMNS).writeheader()

    def log(self, event: str, track_id=None, name=None, distance=None, detail=None):
        row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "event": event,
            "track_id": track_id if track_id is not None else "",
            "name": name or "",
            "distance": f"{distance:.4f}" if distance is not None else "",
            "detail": detail or "",
        }
        with self._lock:
            with open(self.path, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=self.COLUMNS).writerow(row)
        # Also print to stdout so you can tail the log
        parts = [row["timestamp"], f"[{event}]"]
        if track_id is not None:
            parts.append(f"id={track_id}")
        if name:
            parts.append(f"name={name}")
        if distance is not None:
            parts.append(f"dist={row['distance']}")
        if detail:
            parts.append(detail)
        print(" ".join(parts))


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(
    db_folder,
    rtsp_urls,
    threshold=THRESHOLD,
    face_retry_frames=FACE_RETRY_FRAMES,
    person_skip=PERSON_SKIP,
    log_file=LOG_FILE,
):
    logger = EventLogger(log_file)
    logger.log("PIPELINE_START", detail=f"db={db_folder} threshold={threshold}")

    # ── Models ──────────────────────────────────────────────────────────────
    weights_dir = Path(__file__).parent / "weights"
    yolo_face = YOLO(str(weights_dir / "yolov12m-face.pt")).to(device)
    yolo_person = YOLO(str(weights_dir / "yolov8n.pt")).to(device)
    tracker     = StrongSort(
            reid_weights=weights_dir / "osnet_x0_25_msmt17.pt",
            device=device,
            half=device == "cuda:0",
        )
    resnet = InceptionResnetV1(pretrained="vggface2").to(device).eval()
    with torch.no_grad():
        resnet(torch.zeros(1, 3, 160, 160).to(device))

    manager = EmbeddingManager(db_config=db_folder)
    manager.load_db_into_memory()
    logger.log("MODELS_LOADED")

    # ── Shared state ─────────────────────────────────────────────────────────
    face_queue   = queue.Queue(maxsize=4)
    identity_map = {}          # track_id -> name
    identity_lock = threading.Lock()

    # ── Helpers ──────────────────────────────────────────────────────────────
    def preprocess_face(face_img):
        face_img = cv2.resize(face_img, (160, 160))
        face_img = face_img.astype(np.float32) / 255.0
        face_img = (face_img - 0.5) / 0.5
        face_img = np.transpose(face_img, (2, 0, 1))
        return torch.tensor(face_img).unsqueeze(0)

    def face_worker():
        while True:
            try:
                track_id, crop = face_queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                results = yolo_face(crop, verbose=False, conf=0.6)
                if len(results[0].boxes) > 0:
                    x1, y1, x2, y2 = map(int, results[0].boxes.xyxy[0])
                    face = crop[y1:y2, x1:x2]
                    if face.size > 0:
                        face_tensor = preprocess_face(face).to(device)
                        with torch.no_grad():
                            emb = resnet(face_tensor).cpu().numpy().squeeze()
                        name, dist = manager.search_face(emb)
                        if dist < threshold and name != "Unknown":
                            with identity_lock:
                                previous = identity_map.get(track_id)
                                identity_map[track_id] = name
                            if previous != name:
                                logger.log("FACE_IDENTIFIED", track_id=track_id,
                                           name=name, distance=dist)
                        else:
                            logger.log("FACE_UNKNOWN", track_id=track_id,
                                       distance=dist,
                                       detail=f"best_match={name}")
                else:
                    logger.log("FACE_NOT_DETECTED", track_id=track_id)
            except Exception as e:
                logger.log("FACE_ERROR", track_id=track_id, detail=str(e))
            face_queue.task_done()

    threading.Thread(target=face_worker, daemon=True).start()

    # ── Camera ────────────────────────────────────────────────────────────────
    class ThreadedCamera:
        def __init__(self, rtsp_urls):
            self.cap = self._get_working_stream(rtsp_urls)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.ret, self.frame = self.cap.read()
            self.stopped = False
            threading.Thread(target=self._update, daemon=True).start()

        def _get_working_stream(self, rtsp_urls):
            for url in rtsp_urls:
                cap = cv2.VideoCapture(url)
                if cap.isOpened():
                    logger.log("CAMERA_OPENED", detail=f"url={url}")
                    return cap
            raise RuntimeError(f"Could not open any RTSP stream from: {rtsp_urls}")

        def _update(self):
            while not self.stopped:
                ret, frame = self.cap.read()
                if ret:
                    self.ret, self.frame = ret, frame

        def read(self):
            return self.ret, self.frame

        def stop(self):
            self.stopped = True
            self.cap.release()

    cam = ThreadedCamera(rtsp_urls=rtsp_urls)
    time.sleep(1)

    # ── Main loop ─────────────────────────────────────────────────────────────
    frame_idx       = 0
    prev_dets       = np.empty((0, 6))
    track_ages      = {}
    track_last_face = {}
    active_tracks   = set()   # tracks currently visible
    fps_counter     = 0
    fps_start       = time.time()

    logger.log("LOOP_START")
    try:
        while True:
            ret, frame = cam.read()
            if not ret:
                logger.log("FRAME_READ_FAILED")
                break

            frame_idx   += 1
            fps_counter += 1
            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Person detection (every N frames)
            if frame_idx % person_skip == 0:
                results   = yolo_person(frame, classes=0, verbose=False, conf=0.5)
                prev_dets = (
                    results[0].boxes.data.cpu().numpy()
                    if len(results[0].boxes) > 0
                    else np.empty((0, 6))
                )

            current_ids = set()

            if prev_dets.shape[0] > 0:
                tracks = tracker.update(prev_dets, rgb)
                for track in tracks:
                    x1, y1, x2, y2, track_id = map(int, track[:5])
                    h, w = frame.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)

                    current_ids.add(track_id)
                    track_ages[track_id] = track_ages.get(track_id, 0) + 1

                    # Log new track appearing
                    if track_id not in active_tracks:
                        active_tracks.add(track_id)
                        logger.log("PERSON_ENTERED", track_id=track_id)

                    with identity_lock:
                        known = identity_map.get(track_id, "Unknown") != "Unknown"

                    last = track_last_face.get(track_id, -face_retry_frames)
                    if (
                        not known
                        and track_ages[track_id] > 3
                        and (frame_idx - last) >= face_retry_frames
                    ):
                        crop = rgb[y1:y2, x1:x2]
                        if crop.size > 0:
                            try:
                                face_queue.put_nowait((track_id, crop.copy()))
                                track_last_face[track_id] = frame_idx
                            except queue.Full:
                                pass

            # Log tracks that have disappeared
            gone = active_tracks - current_ids
            for track_id in gone:
                active_tracks.discard(track_id)
                with identity_lock:
                    name = identity_map.pop(track_id, "Unknown")
                logger.log("PERSON_LEFT", track_id=track_id, name=name,
                           detail=f"age={track_ages.get(track_id, 0)}_frames")

            # Log FPS every 5 seconds
            if time.time() - fps_start >= 5.0:
                fps = fps_counter / 5
                fps_counter = 0
                fps_start   = time.time()
                logger.log("FPS", detail=f"{fps:.1f}")

    except KeyboardInterrupt:
        logger.log("INTERRUPTED_BY_USER")
    finally:
        cam.stop()
        logger.log("PIPELINE_STOPPED",
                   detail=f"total_frames={frame_idx} log={log_file}")