import queue
import threading
import time
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from boxmot import StrongSort
from facenet_pytorch import InceptionResnetV1
from embedding_manager import EmbeddingManager
 
 
#--------------------------- Config ---------------------------


THRESHOLD= 1.0        # max distance between embeddings (smaller = stricter matching)
FACE_RETRY_FRAMES= 10 # if a face is unknown --> retry after 10 frames
CAMERA_SRC = 0        # only one camera
PERSON_SKIP = 2       # detect people every 2 frames to reduce gpu load

#------------------------------------------------------------
device = "cuda:0" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

# ------------------- MODELS -------------------

yolo_person = YOLO("yolov8n.pt").to(device)
yolo_face= YOLO("yolov12m-face.pt").to(device)

# Keep the same ID for the same person across frames / StrongSORT is using OSNet internally
tracker = StrongSort(reid_weights=Path("osnet_x0_25_msmt17.pt"),
                     device=device,
                     half=device == "cuda:0",
                     )
# facenet model
resnet = InceptionResnetV1(pretrained="vggface2").to(device).eval()
with torch.no_grad():
    resnet(torch.zeros(1, 3, 160, 160).to(device))
# Faiss
manager = EmbeddingManager(db_folder="embeddings_db")
manager.load_db_into_memory()

face_queue = queue.Queue(maxsize=4)
identity_map={}
identity_lock=threading.Lock()

# ------------------- FACE -------------------
# 
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
            # [1] YOLOFACE: detect face inside person box
            results=yolo_face(crop, verbose=False, conf=0.6)

            if len(results[0].boxes) > 0:
                x1, y1, x2, y2 = map(int, results[0].boxes.xyxy[0])
                # extract face area
                face = crop[y1:y2, x1:x2]

                if face.size > 0:
                    face_tensor = preprocess_face(face).to(device)

                    with torch.no_grad():
                        # [2] Facenet:  get embedding 512d vector
                        emb = resnet(face_tensor).cpu().numpy().squeeze()

                    name, dist = manager.search_face(emb)

                    if dist<THRESHOLD and name != "Unknown":
                        with identity_lock:
                            # FUSION (name + ID)
                            identity_map[track_id] = name

        except Exception as e:
            print("Face error:", e)

        face_queue.task_done()

threading.Thread(target=face_worker, daemon=True).start()

# ------------------- CAMERA -------------------
class ThreadedCamera:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)

        # 480p for speed (IMPORTANT)--> 1080p means more pixels --> higher gpu load
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            if ret:
                self.ret, self.frame = ret,frame

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        self.cap.release()

# ------------------- MAIN -------------------

cam = ThreadedCamera(CAMERA_SRC)
time.sleep(1)
track_ages= {} 
track_last_face= {}

frame_idx = 0
prev_dets=np.empty((0, 6))

# FPS calculation
fps_counter = 0
fps_start = time.time()
fps = 0
while True:
    ret, frame = cam.read()
    if not ret:
        break

    frame_idx += 1
    fps_counter += 1

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # PERSON DETECTION  
    if frame_idx % PERSON_SKIP == 0:
        results = yolo_person(frame, classes=0, verbose=False, conf=0.5)
        prev_dets = results[0].boxes.data.cpu().numpy() \
            if len(results[0].boxes) > 0 else np.empty((0, 6))

    dets = prev_dets
    current_ids =[]
    if dets.shape[0] > 0:
        tracks=tracker.update(dets, rgb)

        for track in tracks:
            x1,y1, x2, y2, track_id =map(int, track[:5])
            current_ids.append(track_id)
            h,w = frame.shape[:2]
            x1,y1= max(0, x1),max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            track_ages[track_id] = track_ages.get(track_id, 0) + 1

            with identity_lock:
                known =identity_map.get(track_id, "Unknown") != "Unknown"

            last = track_last_face.get(track_id, -FACE_RETRY_FRAMES)
            if not known and track_ages[track_id] > 3 and (frame_idx - last) >= FACE_RETRY_FRAMES:
                crop = rgb[y1:y2, x1:x2]
                if crop.size > 0:
                    try:
                        face_queue.put_nowait((track_id, crop.copy()))
                        track_last_face[track_id] = frame_idx

                    except queue.Full:
                        pass

            with identity_lock:
                name = identity_map.get(track_id, "Unknown")

            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{name} ID:{track_id}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, color, 2)

    # FPS CALCULATION: why it exceeds 30 fps and the laptop camera is 30 fps?
    if time.time()-fps_start >= 1.0:
        fps = fps_counter
        fps_counter = 0
        fps_start = time.time()

    cv2.putText(frame, f"FPS: {fps}",(20, 40),cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

    cv2.imshow("Pipeline", frame)
    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
        break

cam.stop()
cv2.destroyAllWindows()