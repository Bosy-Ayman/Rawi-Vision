#!/usr/bin/env python3

import json
import sqlite3
import argparse
import time
import os
from pathlib import Path

# Load environment variables from search/.env if it exists
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                try:
                    key, val = line.strip().split("=", 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")
                except ValueError:
                    pass
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- Configurable models ---

VLM_MODEL = "HuggingFaceTB/SmolVLM-Instruct"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"   # 384-dim
EMBEDDING_DIM = 384
COMBINED_DIM = EMBEDDING_DIM * 3   # [objects, caption, motion]

# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------

@dataclass
class Frame:
    frame_id: int
    timestamp: float
    description: str

# ----------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------

class VideoDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init()

    def _init(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS frames (
                    frame_id INTEGER PRIMARY KEY,
                    timestamp REAL,
                    description TEXT
                )
            """)
            conn.commit()
            
            # Dynamic migration: add tracks column if not already present
            try:
                conn.execute("ALTER TABLE frames ADD COLUMN tracks TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass

    def save(self, frame_id: int, timestamp: float, description: str, tracks: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO frames VALUES (?, ?, ?, ?)",
                (frame_id, timestamp, description, tracks)
            )
            conn.commit()

# ----------------------------------------------------------------------
# FAISS Index (1152‑dim, inner product with L2‑normalized vectors)
# ----------------------------------------------------------------------

class FAISSIdx:
    def __init__(self, faiss_path: str, map_path: str):
        self.faiss_path = faiss_path
        self.map_path = map_path
        self.map: dict[int, int] = {}
        self._load_or_create()

    def _load_or_create(self):
        import faiss
        if Path(self.faiss_path).exists():
            print(f"[INFO] Loading existing FAISS index from {self.faiss_path}")
            self.index = faiss.read_index(self.faiss_path)
            if self.index.d != COMBINED_DIM:
                raise ValueError("Existing FAISS index dimension mismatch")
            with open(self.map_path) as f:
                self.map = {int(k): v for k, v in json.load(f).items()}
            print(f"[INFO] Loaded {len(self.map)} frame mappings")
        else:
            print(f"[INFO] Creating new FAISS index (dim={COMBINED_DIM})")
            self.index = faiss.IndexFlatIP(COMBINED_DIM)

    def add(self, frame_id: int, embedding: np.ndarray):
        emb = embedding.astype(np.float32).reshape(1, -1)
        self.index.add(emb)
        self.map[len(self.map)] = frame_id

    def save(self):
        import faiss
        faiss.write_index(self.index, self.faiss_path)
        with open(self.map_path, "w") as f:
            json.dump(self.map, f)
        print(f"[INFO] Saved FAISS index with {len(self.map)} frames")

# ----------------------------------------------------------------------
# Multimodal Frame Encoder (YOLO + VLM + Optical Flow)
# ----------------------------------------------------------------------

class FrameEncoder:
    def __init__(self, use_vlm: bool = True, device: Optional[str] = None):
        self.device = device if device is not None else DEVICE
        # 1. Load VLM first when memory is completely fresh and unfragmented
        self.vlm = None
        self.vlm_proc = None
        if use_vlm:
            print(f"[INFO] Loading VLM on {self.device} (this may take a minute)...")
            try:
                if self.device == "cuda":
                    from transformers import BitsAndBytesConfig
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.bfloat16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4"
                    )
                    self.vlm = AutoModelForImageTextToText.from_pretrained(
                        VLM_MODEL,
                        quantization_config=quantization_config,
                        device_map="auto",
                        low_cpu_mem_usage=True,
                        trust_remote_code=True
                    )
                else:
                    self.vlm = AutoModelForImageTextToText.from_pretrained(
                        VLM_MODEL,
                        torch_dtype=torch.float32,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True
                    )
                self.vlm_proc = AutoProcessor.from_pretrained(VLM_MODEL)
                print("[INFO] VLM loaded successfully")
            except Exception as e:
                print(f"[WARN] Failed to load VLM: {e}")
                self.vlm = None

        # 2. Load YOLO model
        from ultralytics import YOLO
        print("[INFO] Loading YOLO model on CPU...")
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        backend_dir = root_dir / "backend"
        yolo_path = backend_dir / "yolov8x.pt"
        if not yolo_path.exists():
            yolo_path = root_dir / "yolov8x.pt"
        self.yolo_model = YOLO(str(yolo_path))
        self.yolo_model = self.yolo_model.to("cpu")

        # 3. Load EasyOCR reader
        import easyocr
        print("[INFO] Loading EasyOCR reader on CPU...")
        try:
            self.ocr_reader = easyocr.Reader(['en'], gpu=False)
            print("[INFO] EasyOCR reader loaded")
        except Exception as e:
            print(f"[WARN] Failed to load EasyOCR: {e}")
            self.ocr_reader = None

        # 4. Load Sentence Transformer embedding model
        from sentence_transformers import SentenceTransformer
        print("[INFO] Loading embedding model on CPU...")
        self.emb_model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

        # 5. Load Face Recognition if database config/environment is available
        self.face_recognition_enabled = False
        try:
            import sys
            root_dir = Path(__file__).resolve().parent.parent.parent.parent
            backend_dir = root_dir / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            
            from camera_ingestion.ai.embedding_manager import EmbeddingManager
            from facenet_pytorch import InceptionResnetV1
            from ultralytics import YOLO
            
            print("[INFO] Loading Face Recognition components...")
            db_config = {
                "host": os.getenv("DB_HOST", "127.0.0.1"),
                "port": int(os.getenv("DB_PORT", 5433)),
                "dbname": os.getenv("DB_NAME", "rawivision_db"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "postgres"),
            }
            self.face_manager = EmbeddingManager(db_config=db_config)
            self.face_manager.load_db_into_memory()
            
            face_weights = backend_dir / "camera_ingestion" / "ai" / "weights" / "yolov12m-face.pt"
            self.yolo_face = YOLO(str(face_weights)).to("cpu")
            self.resnet = InceptionResnetV1(pretrained="vggface2").to("cpu").eval()
            self.face_recognition_enabled = True
            print("[INFO] Face Recognition components loaded successfully on CPU")
        except Exception as e:
            print(f"[WARN] Failed to load Face Recognition: {e}")

        print("[INFO] FrameEncoder ready")

    def detect_objects(self, frame_bgr: np.ndarray) -> List[str]:
        try:
            results = self.yolo_model(frame_bgr, conf=0.5, verbose=False)
            objects = set()
            for r in results:
                for cls_id in r.boxes.cls:
                    objects.add(self.yolo_model.names[int(cls_id)])
            return sorted(objects)
        except Exception as e:
            print(f"[WARN] Object detection failed: {e}")
            return []

    def extract_text(self, frame_bgr: np.ndarray) -> List[str]:
        if getattr(self, "ocr_reader", None) is None:
            return []
        try:
            results = self.ocr_reader.readtext(frame_bgr, detail=0)
            words = set()
            for r in results:
                clean_word = r.strip()
                if clean_word and len(clean_word) > 1:
                    words.add(clean_word)
            return sorted(list(words))
        except Exception as e:
            print(f"[WARN] OCR text extraction failed: {e}")
            return []

    def track_subjects(self, frame_bgr: np.ndarray) -> List[int]:
        try:
            # Persistent multi-object tracking via YOLOv8 built-in ByteTrack/BoT-SORT
            results = self.yolo_model.track(frame_bgr, persist=True, conf=0.5, verbose=False)
            track_ids = []
            for r in results:
                if r.boxes is not None and r.boxes.id is not None:
                    for cls_id, track_id in zip(r.boxes.cls, r.boxes.id):
                        if int(cls_id) == 0:  # 0 is the COCO person class
                            track_ids.append(int(track_id))
            return sorted(list(set(track_ids)))
        except Exception:
            return []

    def motion_vector(self, frame_bgr: np.ndarray,
                      prev_frame_bgr: Optional[np.ndarray]) -> Tuple[float, Optional[float]]:
        try:
            if prev_frame_bgr is None:
                return 0.0, None
            gray1 = cv2.cvtColor(prev_frame_bgr, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(gray1, gray2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            avg_mag = float(np.mean(mag))
            hist, _ = np.histogram(ang, bins=16, range=(0, 2*np.pi))
            dominant_bin = np.argmax(hist)
            angle_deg = float(dominant_bin * (360/16))
            return avg_mag, angle_deg
        except Exception as e:
            print(f"[WARN] Motion detection failed: {e}")
            return 0.0, None

    def motion_to_text(self, avg_mag: float, angle_deg: Optional[float]) -> str:
        if avg_mag < 0.2:
            return "static scene"
        elif avg_mag < 1.0:
            speed = "slow motion"
        elif avg_mag < 3.0:
            speed = "moderate motion"
        else:
            speed = "fast motion"

        if angle_deg is not None:
            dirs = ["rightward", "down-right", "downward", "down-left",
                    "leftward", "up-left", "upward", "up-right"]
            idx = int((angle_deg + 22.5) // 45) % 8
            direction = dirs[idx]
            return f"{speed} {direction}"
        return speed

    def describe_vlm(self, frame_rgb: np.ndarray, object_hint: str = "", objects: List[str] = None, ocr_words: List[str] = None, motion_text: str = "") -> str:
        if self.vlm is None:
            return self._fallback(frame_rgb, objects, ocr_words, motion_text)
        try:
            img = Image.fromarray(frame_rgb)
            prompt = "Describe this image in detail, focusing factually on the main action, the people, and the environment. Write only the objective scene description. IMPORTANT: Do NOT mention, describe, or reference any camera names, date/time watermarks, or text overlays (such as 'Camera 01' or timestamps) that appear on the screen."
            messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
            prompt = self.vlm_proc.apply_chat_template(messages, add_generation_prompt=True)
            inputs = self.vlm_proc(text=prompt, images=img, return_tensors="pt").to(self.device)
            with torch.no_grad():
                out = self.vlm.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    repetition_penalty=1.2
                )
            out = out[:, inputs["input_ids"].shape[1]:]
            return self.vlm_proc.batch_decode(out, skip_special_tokens=True)[0].strip()
        except Exception as e:
            print(f"[WARN] VLM inference failed: {e}")
            return self._fallback(frame_rgb, objects, ocr_words, motion_text)

    def _fallback(self, frame_rgb: np.ndarray, objects: List[str] = None, ocr_words: List[str] = None, motion_text: str = "") -> str:
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        brightness = np.mean(gray)
        light = "bright" if brightness > 150 else "dim" if brightness < 100 else "normally lit"
        edges = cv2.Canny(gray, 100, 200)
        detail = "highly detailed" if np.sum(edges > 0) / edges.size > 0.05 else "simple"
        
        desc = f"A {light}, {detail} surveillance camera frame."
        if objects:
            desc += f" Visible elements: {', '.join(objects)}."
        if ocr_words:
            desc += f" Detected text labels: {', '.join(ocr_words)}."
        if motion_text and "static" not in motion_text:
            desc += f" Motion profile: {motion_text}."
        return desc

    def encode_frame(self, frame_bgr: np.ndarray,
                     prev_frame_bgr: Optional[np.ndarray] = None) -> Tuple[np.ndarray, str, List[int]]:
        # Tracks
        track_ids = self.track_subjects(frame_bgr)

        # Objects
        objects = self.detect_objects(frame_bgr)
        obj_text = "Objects: " + ", ".join(objects) if objects else "no objects"

        # OCR text extraction
        ocr_words = self.extract_text(frame_bgr)
        ocr_text = "Text detected: " + ", ".join(ocr_words) if ocr_words else "no text"

        # Fuse OCR with objects text for embedding component (keeps total FAISS dimension exactly 1152)
        obj_ocr_text = obj_text
        if ocr_words:
            obj_ocr_text += ", with detected text: " + ", ".join(ocr_words)

        # Motion
        avg_mag, angle = self.motion_vector(frame_bgr, prev_frame_bgr)
        motion_desc = self.motion_to_text(avg_mag, angle)
        motion_text = "Motion: " + motion_desc

        # VLM caption (falls back to premium synthesis if offline)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        desc_text = self.describe_vlm(frame_rgb, obj_text, objects, ocr_words, motion_desc)

        # 4. Run Face Recognition
        identified_names = []
        if self.face_recognition_enabled:
            try:
                face_results = self.yolo_face(frame_bgr, verbose=False, conf=0.3)
                for r in face_results:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        h, w = frame_bgr.shape[:2]
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w, x2), min(h, y2)
                        face_crop = frame_bgr[y1:y2, x1:x2]
                        if face_crop.size > 0:
                            # Preprocess face
                            face_crop_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                            face_resized = cv2.resize(face_crop_rgb, (160, 160))
                            face_norm = face_resized.astype(np.float32) / 255.0
                            face_norm = (face_norm - 0.5) / 0.5
                            face_tensor = torch.tensor(np.transpose(face_norm, (2, 0, 1))).unsqueeze(0).to("cpu")
                            with torch.no_grad():
                                emb = self.resnet(face_tensor).cpu().numpy().squeeze()
                            emp_id, name, dist = self.face_manager.search_face(emb)
                            if dist < 1.0 and name != "Unknown":
                                identified_names.append(name)
            except Exception as face_err:
                print(f"[WARN] Face Recognition failed during frame encoding: {face_err}")

        # If any known people are identified, append them to the description
        names_str = "none"
        if identified_names:
            unique_names = sorted(list(set(identified_names)))
            names_str = ", ".join(unique_names)
            desc_text = f"{desc_text} Identified person(s): {names_str}."

        # Embed each textual component
        emb_obj = self.emb_model.encode(obj_ocr_text, convert_to_numpy=True)
        emb_desc = self.emb_model.encode(desc_text, convert_to_numpy=True)
        emb_mot = self.emb_model.encode(motion_text, convert_to_numpy=True)

        # Concatenate & normalize
        combined = np.concatenate([emb_obj, emb_desc, emb_mot])
        norm = np.linalg.norm(combined) + 1e-8
        combined = combined / norm

        full_desc = f"{desc_text} | {obj_ocr_text} | {motion_text} | {ocr_text} | Identified People: {names_str}"
        return combined.astype(np.float32), full_desc, track_ids

# ----------------------------------------------------------------------
# Main indexing loop
# ----------------------------------------------------------------------

def index_video(source: str, sampling: int, db_path="video.db",
                faiss_path="video.faiss", map_path="video.json"):
    # Resolve output paths to data/ subfolder dynamically
    def resolve_output_path(filename: str) -> str:
        if Path(filename).is_absolute():
            return filename
        # Check if running in core/, output to ../data/filename
        p_parent_data = Path(__file__).resolve().parent.parent / "data"
        if p_parent_data.exists():
            return str(p_parent_data / filename)
        # Check if running in search/, output to data/filename
        p_data = Path("data")
        if p_data.exists():
            return str(p_data / filename)
        return filename

    resolved_db = resolve_output_path(db_path)
    resolved_faiss = resolve_output_path(faiss_path)
    resolved_map = resolve_output_path(map_path)

    db = VideoDB(resolved_db)
    faiss_idx = FAISSIdx(resolved_faiss, resolved_map)
    encoder = FrameEncoder(use_vlm=True)

    if source == "0":
        cap = cv2.VideoCapture(0)
    else:
        if not Path(source).exists():
            raise FileNotFoundError(f"Video file not found: {source}")
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {source}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[INFO] FPS: {fps:.1f} | Total frames: {total_frames} | Sampling every {sampling} frames")

    indexed_frame = 0
    sampled_count = 0
    prev_frame = None
    start = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            indexed_frame += 1
            if indexed_frame % sampling != 0:
                prev_frame = frame
                continue

            sampled_count += 1
            timestamp = (indexed_frame / fps) if fps > 0 else time.time() - start

            t0 = time.time()
            embedding, full_desc, track_ids = encoder.encode_frame(frame, prev_frame)
            elapsed = time.time() - t0

            tracks_str = ",".join(map(str, track_ids))
            db.save(indexed_frame, timestamp, full_desc, tracks_str)
            faiss_idx.add(indexed_frame, embedding)

            print(f"[{sampled_count}] Frame {indexed_frame}/{total_frames} | {full_desc[:80]}... (tracks: {tracks_str}) ({elapsed:.2f}s)")
            prev_frame = frame

    except KeyboardInterrupt:
        print("[INFO] Interrupted by user")
    finally:
        cap.release()
        faiss_idx.save()
    print(f"\n[SUCCESS] Indexed {sampled_count} frames (from {indexed_frame} total)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline video indexer")
    parser.add_argument("source", help="Video file path or '0' for webcam")
    parser.add_argument("--sampling", type=int, default=16, help="Sample every N-th frame")
    parser.add_argument("--db", default="video.db")
    parser.add_argument("--faiss", default="video.faiss")
    parser.add_argument("--map", default="video.json")
    args = parser.parse_args()

    index_video(args.source, args.sampling, args.db, args.faiss, args.map)