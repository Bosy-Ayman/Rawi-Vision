import argparse
import csv
import json
import queue
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
import psutil
import torch

from ultralytics import YOLO
from boxmot import StrongSort
from facenet_pytorch import MTCNN, InceptionResnetV1
from embedding_manager import EmbeddingManager

#--------------------------- CONFIG ------------------------------------------------

THRESHOLD         = 1.0
FACE_RETRY_FRAMES = 15    # frames between recognition attempts per unknown track
SMOOTH_N          = 30    # rolling window size for HUD averages
MEM_INTERVAL      = 1.0   # seconds between memory snapshots


# ══════════════════════════════════════════════════════════════════
# 1.  Args
# ══════════════════════════════════════════════════════════════════
parser = argparse.ArgumentParser()
parser.add_argument("--gt",       default=None,                    help="Ground-truth CSV path")
parser.add_argument("--duration", type=float, default=None,        help="Auto-stop after N seconds")
parser.add_argument("--out",      default="benchmark_report.json", help="Report output path")
parser.add_argument("--camera",   type=int,   default=0,           help="Camera index")
args = parser.parse_args()


# ══════════════════════════════════════════════════════════════════
# 2.  Ground-truth loader
# ══════════════════════════════════════════════════════════════════
gt_lookup: dict = {}
if args.gt:
    with open(args.gt, newline="") as f:
        for row in csv.DictReader(f):
            gt_lookup[int(float(row["timestamp_s"]))] = row["true_name"].strip()
    print(f"✓ Loaded {len(gt_lookup)} GT entries from {args.gt}")


# ══════════════════════════════════════════════════════════════════
# 3.  Device
# ══════════════════════════════════════════════════════════════════
device = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"✓ Using device: {device}")

#---------------- Models ---------------------------------
yolo_model = YOLO("yolov8n.pt").to(device)

tracker = StrongSort(
    reid_weights=Path("osnet_x0_25_msmt17.pt"),
    device=device,
    half=True if device == "cuda:0" else False,
    max_age=30,
    max_dist=0.35,
    max_iou_dist=0.7,
    ema_alpha=0.9,
)

mtcnn  = MTCNN(keep_all=False, device=device)
resnet = InceptionResnetV1(pretrained="vggface2", device=device).eval()
print(f"✓ ResNet on: {next(resnet.parameters()).device}")

# GPU warm-up — eliminates the cold-start spike on the first real face call
print("Warming up GPU...")
with torch.no_grad():
    _dummy = torch.zeros(1, 3, 160, 160, device=device)
    resnet(_dummy)
del _dummy
print("✓ GPU warm-up done")

manager = EmbeddingManager(db_folder="embeddings_db")
manager.load_db_into_memory()


# ══════════════════════════════════════════════════════════════════
# 5.  Async camera
# ══════════════════════════════════════════════════════════════════
class ThreadedCamera:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        threading.Thread(target=self._update, daemon=True).start()

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


# ══════════════════════════════════════════════════════════════════
# 6.  Background face-recognition thread
# ══════════════════════════════════════════════════════════════════
face_queue    = queue.Queue(maxsize=4)
identity_map  = {}
identity_lock = threading.Lock()

face_times      = deque(maxlen=SMOOTH_N)
face_times_lock = threading.Lock()
all_face_times  = []   # full history for final report

def face_worker():
    while True:
        try:
            track_id, crop = face_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            t0 = time.perf_counter()
            face_tensor = mtcnn(crop)
            if face_tensor is not None:
                face_tensor = face_tensor.to(device)
                with torch.no_grad():
                    emb = resnet(face_tensor.unsqueeze(0)).cpu().numpy().squeeze()
                if emb.ndim > 0 and emb.size > 0:
                    name, dist = manager.search_face(emb)
                    if dist < THRESHOLD and name != "Unknown":
                        with identity_lock:
                            identity_map[track_id] = name
            dt = time.perf_counter() - t0
            with face_times_lock:
                face_times.append(dt)
                all_face_times.append(dt)
        except Exception as e:
            print(f"[face_worker] track {track_id}: {e}")
        finally:
            face_queue.task_done()

threading.Thread(target=face_worker, daemon=True).start()


# ══════════════════════════════════════════════════════════════════
# 7.  Benchmark state
# ══════════════════════════════════════════════════════════════════
stage_times = {k: deque(maxlen=SMOOTH_N) for k in ("yolo", "tracker", "total")}
fps_deque   = deque(maxlen=SMOOTH_N)

all_fps      = []
all_totals   = []
all_yolo_t   = []
all_tracker_t= []

memory_samples = []

def sample_memory():
    s = {
        "t":      time.perf_counter() - pipeline_start,
        "ram_mb": psutil.Process().memory_info().rss / 1e6,
    }
    if device.startswith("cuda"):
        s["gpu_alloc_mb"]    = torch.cuda.memory_allocated(0) / 1e6
        s["gpu_reserved_mb"] = torch.cuda.memory_reserved(0) / 1e6
    memory_samples.append(s)

track_history   = defaultdict(list)
prev_ids        = {}
id_switches     = 0
seen_track_ids  = set()

face_preds = defaultdict(list)
TP = FP = TN = FN = 0

track_ages      = {}
track_last_face = {}

pipeline_start = time.perf_counter()
last_mem_t     = pipeline_start
last_fps_t     = pipeline_start
frame_idx      = 0


# ══════════════════════════════════════════════════════════════════
# 8.  HUD drawing
# ══════════════════════════════════════════════════════════════════
def ms_avg(q):
    return sum(q) / len(q) * 1000 if q else 0.0

def draw_hud(frame, fps, elapsed):
    global TP, FP, TN, FN
    h, w = frame.shape[:2]
    overlay = frame.copy()

    has_face_acc = (TP + FP + TN + FN) > 0
    ph = 305 + (57 if has_face_acc else 0)
    pw = 335
    px = w - pw - 10

    cv2.rectangle(overlay, (px, 10), (px + pw, 10 + ph), (10, 10, 10), -1)
    frame[:] = cv2.addWeighted(overlay, 0.72, frame, 0.28, 0)

    mem = memory_samples[-1] if memory_samples else {}
    with face_times_lock:
        face_ms = ms_avg(face_times)

    lines = [
        # (text, color, bold)
        ("BENCHMARK",                                          (0, 220, 255),   True),
        (f"Runtime       {elapsed:>6.0f} s",                  (130, 130, 130), False),
        ("",                                                   (0,0,0),         False),
        ("SPEED",                                              (0, 180, 255),   True),
        (f"FPS           {fps:>7.1f}",                        (0, 255, 150),   False),
        (f"Frame total   {ms_avg(stage_times['total']):>6.1f} ms", (180,180,180), False),
        (f"YOLO          {ms_avg(stage_times['yolo']):>6.1f} ms",  (180,180,180), False),
        (f"Tracker       {ms_avg(stage_times['tracker']):>6.1f} ms",(180,180,180),False),
        (f"Face (async)  {face_ms:>6.1f} ms",                (0, 200, 120),   False),
        ("",                                                   (0,0,0),         False),
        ("TRACKING",                                           (0, 180, 255),   True),
        (f"ID switches   {id_switches:>6d}",                  (180,180,180),   False),
        (f"Tracks seen   {len(seen_track_ids):>6d}",          (180,180,180),   False),
        ("",                                                   (0,0,0),         False),
        ("MEMORY",                                             (0, 180, 255),   True),
        (f"RAM           {mem.get('ram_mb', 0):>6.1f} MB",    (180,180,180),   False),
        (f"GPU alloc     {mem.get('gpu_alloc_mb', 0):>6.1f} MB",  (180,180,180), False),
        (f"GPU reserved  {mem.get('gpu_reserved_mb', 0):>6.1f} MB",(180,180,180),False),
    ]

    if has_face_acc:
        total_ev  = TP + FP + TN + FN
        acc       = (TP + TN) / total_ev * 100
        precision = TP / (TP + FP) * 100 if (TP + FP) > 0 else 0
        recall    = TP / (TP + FN) * 100 if (TP + FN) > 0 else 0
        lines += [
            ("",                                               (0,0,0),         False),
            ("FACE ACCURACY",                                  (0, 180, 255),   True),
            (f"Accuracy      {acc:>5.1f}%",                   (180,180,180),   False),
            (f"Precision     {precision:>5.1f}%",             (180,180,180),   False),
            (f"Recall        {recall:>5.1f}%",                (180,180,180),   False),
        ]

    y0 = 28
    for text, color, bold in lines:
        cv2.putText(frame, f"  {text}", (px + 6, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color,
                    2 if bold else 1, cv2.LINE_AA)
        y0 += 17


# ══════════════════════════════════════════════════════════════════
# 9.  Main loop
# ══════════════════════════════════════════════════════════════════
cam = ThreadedCamera(args.camera)
time.sleep(1.0)
print("Running — press Q or ESC to quit.")

while True:
    ret, frame = cam.read()
    if not ret:
        break

    t_start   = time.perf_counter()
    elapsed   = t_start - pipeline_start
    frame_idx += 1

    if args.duration and elapsed > args.duration:
        print(f"\n⏱  Duration limit ({args.duration}s) reached.")
        break

    frame = cv2.flip(frame, 1)
    rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    elapsed_sec = int(elapsed)

    if t_start - last_mem_t >= MEM_INTERVAL:
        sample_memory()
        last_mem_t = t_start

    # ── [A] YOLO ──
    t0 = time.perf_counter()
    results = yolo_model(frame, classes=0, verbose=False, conf=0.5)
    yolo_dt = time.perf_counter() - t0
    stage_times["yolo"].append(yolo_dt)
    all_yolo_t.append(yolo_dt)

    dets = results[0].boxes.data.cpu().numpy() if results[0].boxes.data.shape[0] > 0 \
           else np.empty((0, 6))

    current_ids = []

    if dets.shape[0] > 0:
        # ── [B] StrongSORT ──
        t0 = time.perf_counter()
        tracks = tracker.update(dets, rgb)
        trk_dt = time.perf_counter() - t0
        stage_times["tracker"].append(trk_dt)
        all_tracker_t.append(trk_dt)

        for track in tracks:
            x1, y1, x2, y2, track_id = map(int, track[:5])
            current_ids.append(track_id)
            seen_track_ids.add(track_id)

            hh, ww = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(ww, x2), min(hh, y2)

            track_ages[track_id] = track_ages.get(track_id, 0) + 1
            track_history[track_id].append(frame_idx)

            # ── [C] Dispatch face job ──
            with identity_lock:
                known = identity_map.get(track_id, "Unknown") != "Unknown"

            last_attempt = track_last_face.get(track_id, -FACE_RETRY_FRAMES)
            if not known and track_ages[track_id] > 3 \
                    and (frame_idx - last_attempt) >= FACE_RETRY_FRAMES:
                crop = rgb[y1:y2, x1:x2]
                if crop.size > 0:
                    try:
                        face_queue.put_nowait((track_id, crop.copy()))
                        track_last_face[track_id] = frame_idx
                    except queue.Full:
                        pass

            # ── ID-switch detection ──
            with identity_lock:
                name = identity_map.get(track_id, "Unknown")

            if track_id in prev_ids \
                    and prev_ids[track_id] != name \
                    and name != "Unknown" \
                    and prev_ids[track_id] != "Unknown":
                id_switches += 1
            prev_ids[track_id] = name

            # ── GT bookkeeping ──
            if gt_lookup and name != "Unknown":
                face_preds[elapsed_sec].append(name)

            prev_sec = elapsed_sec - 1
            if gt_lookup and prev_sec in gt_lookup and prev_sec in face_preds:
                true_name   = gt_lookup.pop(prev_sec)
                preds       = face_preds.pop(prev_sec, [])
                most_common = max(set(preds), key=preds.count) if preds else "Unknown"
                if true_name == "Unknown":
                    if most_common == "Unknown": TN += 1
                    else:                        FP += 1
                else:
                    if most_common == true_name: TP += 1
                    else:                        FN += 1

            # ── Draw ──
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{name} (ID:{track_id})",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        dead = set(track_ages) - set(current_ids)
        for d in dead:
            track_ages.pop(d, None)
            track_last_face.pop(d, None)

    else:
        tracker.update(np.empty((0, 6)), frame)
        track_ages.clear()
        track_last_face.clear()

    total_dt = time.perf_counter() - t_start
    stage_times["total"].append(total_dt)
    all_totals.append(total_dt)

    now = time.perf_counter()
    fps_deque.append(1.0 / max(now - last_fps_t, 1e-9))
    last_fps_t = now
    fps = sum(fps_deque) / len(fps_deque)
    all_fps.append(fps)

    draw_hud(frame, fps, elapsed)

    cv2.imshow("Optimized Pipeline + Benchmark", frame)
    key = cv2.waitKey(1) & 0xFF
    if key in (ord("q"), 27):
        break


# ══════════════════════════════════════════════════════════════════
# 10.  Final report
# ══════════════════════════════════════════════════════════════════
cam.stop()
cv2.destroyAllWindows()

run_duration = time.perf_counter() - pipeline_start

def _avg(lst):  return round(sum(lst) / len(lst), 3) if lst else None
def _peak(lst): return round(max(lst), 3) if lst else None
def _min(lst):  return round(min(lst), 3) if lst else None
def _ms(lst):   return _avg([x * 1000 for x in lst])
def _ms_p(lst): return _peak([x * 1000 for x in lst])

fragmentations = 0
for frames in track_history.values():
    frames.sort()
    fragmentations += sum(1 for a, b in zip(frames, frames[1:]) if b - a > 5)

with face_times_lock:
    face_hist = list(all_face_times)

ram_vals     = [s["ram_mb"]                 for s in memory_samples]
gpu_alloc    = [s.get("gpu_alloc_mb", 0)    for s in memory_samples]
gpu_reserved = [s.get("gpu_reserved_mb", 0) for s in memory_samples]

report = {
    "run_duration_s": round(run_duration, 2),
    "total_frames":   len(all_fps),

    "fps": {
        "avg":  _avg(all_fps),
        "peak": _peak(all_fps),
        "min":  _min(all_fps),
    },

    "latency_ms": {
        "frame_avg":    _ms(all_totals),
        "frame_peak":   _ms_p(all_totals),
        "yolo_avg":     _ms(all_yolo_t),
        "tracker_avg":  _ms(all_tracker_t),
        "face_avg":     _ms(face_hist),
        "face_peak":    _ms_p(face_hist),
        "face_calls":   len(face_hist),
    },

    "tracking": {
        "unique_tracks":        len(seen_track_ids),
        "id_switches":          id_switches,
        "track_fragmentations": fragmentations,
    },

    "memory": {
        "ram_avg_mb":           _avg(ram_vals),
        "ram_peak_mb":          _peak(ram_vals),
        "gpu_alloc_avg_mb":     _avg(gpu_alloc),
        "gpu_alloc_peak_mb":    _peak(gpu_alloc),
        "gpu_reserved_peak_mb": _peak(gpu_reserved),
    },
}

if (TP + FP + TN + FN) > 0:
    total_ev = TP + FP + TN + FN
    prec = TP / (TP + FP) if (TP + FP) > 0 else 0
    rec  = TP / (TP + FN) if (TP + FN) > 0 else 0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
    report["face_recognition"] = {
        "TP": TP, "FP": FP, "TN": TN, "FN": FN,
        "accuracy_%":  round((TP + TN) / total_ev * 100, 2),
        "precision_%": round(prec * 100, 2),
        "recall_%":    round(rec  * 100, 2),
        "f1_score":    round(f1, 4),
        "FAR_%":       round(FP / (FP + TN) * 100, 2) if (FP + TN) > 0 else None,
        "FRR_%":       round(FN / (FN + TP) * 100, 2) if (FN + TP) > 0 else None,
    }

out_path = Path(args.out)
out_path.write_text(json.dumps(report, indent=2))

print("\n" + "═" * 52)
print("  BENCHMARK REPORT")
print("═" * 52)
print(json.dumps(report, indent=2))
print(f"\n✓ Report saved → {out_path.resolve()}")