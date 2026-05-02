import queue
import threading
import time
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from boxmot import StrongSort
from facenet_pytorch import InceptionResnetV1
from embedding_manager import EmbeddingManager


THRESHOLD = 0.7            
FACE_RETRY_FRAMES = 10      
CAMERA_SRC = 'C:\\Users\\pouss\\Documents\\CSAI\\Rawi-Vision\\ai\\face_recognition\\video\\test4.mp4'       
PERSON_SKIP = 1         


DISPLAY_WIDTH = 960
DISPLAY_HEIGHT = 540
SHOW_PREVIEW = True           # set False to run headless for pure evaluation

# Face detection settings
YOLO_FACE_MODEL = "yolov12m-face.pt"   # try to load this model
YOLO_FACE_CONF = 0.3                  # lower = more detections

# Evaluation output (saved only if source is a video file)
OUTPUT_JSON = "evaluation_results.json"


device = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

print("Loading YOLO person detector...")
yolo_person = YOLO("yolov8n.pt").to(device)

# Face detection – try YOLO face model, fallback to OpenCV
yolo_face = None
face_cascade = None
if Path(YOLO_FACE_MODEL).exists():
    try:
        yolo_face = YOLO(YOLO_FACE_MODEL).to(device)
        print(" Using YOLO face model")
    except Exception as e:
        print(f" Failed to load YOLO face model: {e}")
        yolo_face = None

if yolo_face is None:
    print(" Falling back to OpenCV Haar Cascade for face detection")
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

print("Loading StrongSORT tracker...")
tracker = StrongSort(
    reid_weights=Path("osnet_x0_25_msmt17.pt"),
    device=device,
    half=device == "cuda:0",
    ecc=False
)

print("Loading FaceNet recognition model...")
resnet = InceptionResnetV1(pretrained="vggface2").to(device).eval()
with torch.no_grad():
    resnet(torch.zeros(1, 3, 160, 160).to(device))

print("Loading embedding database...")
manager = EmbeddingManager(db_folder="embeddings_db")
manager.load_db_into_memory()
print(f" Database ready: {manager.index.ntotal} embeddings")

face_queue = queue.Queue(maxsize=8)
identity_map = {}
identity_lock = threading.Lock()
track_ages = {}
track_last_face = {}

# For evaluation logging
recognition_events = []   # list of dicts
frame_results = {}        # frame_idx -> list of tracks with names

def preprocess_face(face_img):
    face_img = cv2.resize(face_img, (160, 160))
    face_img = face_img.astype(np.float32) / 255.0
    face_img = (face_img - 0.5) / 0.5
    face_img = np.transpose(face_img, (2, 0, 1))
    return torch.tensor(face_img).unsqueeze(0)

def face_worker():
    print("Face recognition worker started")
    while True:
        try:
            track_id, crop = face_queue.get(timeout=1)
        except queue.Empty:
            continue

        try:
            # ----- Step 1: detect face inside the person crop -----
            if yolo_face is not None:
                results = yolo_face(crop, verbose=False, conf=YOLO_FACE_CONF)
                if len(results[0].boxes) == 0:
                    continue
                x1, y1, x2, y2 = map(int, results[0].boxes.xyxy[0])
            else:
                gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
                if len(faces) == 0:
                    continue
                x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                x1, y1, x2, y2 = x, y, x + w, y + h

            if x2 <= x1 or y2 <= y1:
                continue
            face = crop[y1:y2, x1:x2]
            if face.size == 0:
                continue

            # ----- Step 2: compute embedding -----
            face_tensor = preprocess_face(face).to(device)
            with torch.no_grad():
                emb = resnet(face_tensor).cpu().numpy().squeeze()

            # ----- Step 3: search in database -----
            name, dist = manager.search_face(emb)

            # ----- Step 4: update identity if match is good -----
            if dist < THRESHOLD and name != "Unknown":
                with identity_lock:
                    identity_map[track_id] = name
                # Log recognition event
                recognition_events.append({
                    "frame": frame_idx,   # will be captured from global
                    "track_id": track_id,
                    "name": name,
                    "distance": float(dist)
                })
                print(f"✅ Recognized {name} (ID:{track_id}, dist={dist:.3f})")
            # Optional debug: print all distances
            # else:
            #     print(f"[DEBUG] Track {track_id} → {name} (dist={dist:.3f})")

        except Exception as e:
            print(f"Face worker error: {e}")

        face_queue.task_done()

# Start one background worker
threading.Thread(target=face_worker, daemon=True).start()

# ========================== CAPTURE (CAMERA vs VIDEO) ==========================
class SmartCapture:
    """Unified capture: threaded for camera, frame‑rate controlled for video files."""
    def __init__(self, src):
        self.src = src
        self.is_camera = isinstance(src, int) or (isinstance(src, str) and src.isdigit())
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            raise ValueError(f"Cannot open source: {src}")

        if self.is_camera:
            # Camera: set resolution and use threaded reading
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.ret, self.frame = self.cap.read()
            self.stopped = False
            self.lock = threading.Lock()
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()
            self.fps = 30  # fallback
        else:
            # Video file: read sequentially at original FPS
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30
            self.frame_delay = 1.0 / self.fps
            self.last_time = time.time()
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            print(f"📹 Video: {Path(src).name}, {self.total_frames} frames, {self.fps:.2f} fps")

    def _update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            with self.lock:
                self.ret = ret
                self.frame = frame
            if not ret:
                break

    def read(self):
        if self.is_camera:
            with self.lock:
                return self.ret, self.frame
        else:
            # Enforce video frame rate
            now = time.time()
            elapsed = now - self.last_time
            if elapsed < self.frame_delay:
                time.sleep(self.frame_delay - elapsed)
            ret, frame = self.cap.read()
            self.last_time = time.time()
            return ret, frame

    def release(self):
        if self.is_camera:
            self.stopped = True
            if hasattr(self, 'thread'):
                self.thread.join(timeout=0.5)
        self.cap.release()

# ========================== MAIN ==========================
cap = SmartCapture(CAMERA_SRC)
time.sleep(0.5 if cap.is_camera else 0.1)

frame_idx = 0
prev_dets = np.empty((0, 6))
fps_counter = 0
fps_start = time.time()
fps = 0

if SHOW_PREVIEW:
    cv2.namedWindow("Pipeline", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Pipeline", DISPLAY_WIDTH, DISPLAY_HEIGHT)

print(" Pipeline started. Press 'q' or ESC to quit.\n")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of video source.")
            break

        frame_idx += 1
        fps_counter += 1
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # ----- Person detection (every PERSON_SKIP frames) -----
        if frame_idx % PERSON_SKIP == 0:
            results = yolo_person(frame, classes=0, verbose=False, conf=0.5)
            boxes_data = results[0].boxes.data
            prev_dets = boxes_data.cpu().numpy() if len(boxes_data) > 0 else np.empty((0, 6))

        dets = prev_dets
        frame_tracks = []   # for logging

        if dets.shape[0] > 0:
            tracks = tracker.update(dets, rgb)
            for track in tracks:
                x1, y1, x2, y2, track_id = map(int, track[:5])
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                track_ages[track_id] = track_ages.get(track_id, 0) + 1

                with identity_lock:
                    known = identity_map.get(track_id, "Unknown") != "Unknown"
                    name = identity_map.get(track_id, "Unknown")

                # Log for this frame (evaluation)
                frame_tracks.append({
                    "track_id": track_id,
                    "name": name,
                    "bbox": [x1, y1, x2, y2]
                })

                # Queue face recognition if unknown
                last = track_last_face.get(track_id, -FACE_RETRY_FRAMES)
                if not known and track_ages[track_id] > 3 and (frame_idx - last) >= FACE_RETRY_FRAMES:
                    # Expand crop a bit for better face detection
                    expand = 20
                    y1_crop = max(0, y1 - expand)
                    y2_crop = min(h, y2 + expand)
                    x1_crop = max(0, x1 - expand)
                    x2_crop = min(w, x2 + expand)
                    crop = rgb[y1_crop:y2_crop, x1_crop:x2_crop]
                    if crop.size > 0:
                        try:
                            face_queue.put_nowait((track_id, crop.copy()))
                            track_last_face[track_id] = frame_idx
                        except queue.Full:
                            pass

                # Draw bounding box and label (if preview enabled)
                if SHOW_PREVIEW:
                    color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = f"{name} ID:{track_id}"
                    cv2.putText(frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Store frame results for evaluation (only if video file)
        if not cap.is_camera:
            frame_results[frame_idx] = frame_tracks

        # ----- FPS calculation and display -----
        if time.time() - fps_start >= 1.0:
            fps = fps_counter
            fps_counter = 0
            fps_start = time.time()

        if SHOW_PREVIEW:
            cv2.putText(frame, f"FPS: {fps}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            # Resize for display (so you can see the whole scene)
            display_frame = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
            cv2.imshow("Pipeline", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
        else:
            # Headless mode: small sleep to avoid 100% CPU
            time.sleep(0.005)

except KeyboardInterrupt:
    print("Interrupted by user")
finally:
    cap.release()
    if SHOW_PREVIEW:
        cv2.destroyAllWindows()

# ========================== EVALUATION SUMMARY (only for video files) ==========================
if not cap.is_camera:
    # Wait a moment for any remaining face queue tasks
    time.sleep(0.5)

    recognized_names = set()
    for ev in recognition_events:
        recognized_names.add(ev["name"])

    first_frame = {}
    for ev in recognition_events:
        name = ev["name"]
        if name not in first_frame:
            first_frame[name] = ev["frame"]

    print("\n" + "="*50)
    print("EVALUATION SUMMARY")
    print("="*50)
    print(f"Total frames processed: {frame_idx}")
    print(f"Total recognition events: {len(recognition_events)}")
    print(f"Unique persons recognised: {len(recognized_names)} -> {', '.join(recognized_names)}")
    if first_frame:
        print("\nFirst recognition per person:")
        for name, frame_nr in first_frame.items():
            print(f"  {name}: frame {frame_nr}")
    print(f"\nAverage FPS: {fps:.1f}")

    # Save detailed results to JSON
    output = {
        "config": {
            "threshold": THRESHOLD,
            "face_confidence": YOLO_FACE_CONF,
            "video_source": str(CAMERA_SRC),
            "total_frames": frame_idx,
            "avg_fps": fps
        },
        "recognition_events": recognition_events,
        "frame_results": {str(k): v for k, v in frame_results.items()}
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n Detailed results saved to {OUTPUT_JSON}")
else:
    print(f"\nLive camera finished. Processed {frame_idx} frames.")
    print(f"   Recognised {len(identity_map)} unique tracks.")