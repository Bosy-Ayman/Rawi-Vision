import json
import sqlite3
import argparse
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

import cv2
import torch
import numpy as np
from PIL import Image
from transformers import AutoModelForVision2Seq, AutoProcessor, pipeline
from sentence_transformers import SentenceTransformer
import faiss
from ultralytics import YOLO

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ------------------- Models -------------------------------------------
VLM_MODEL = "HuggingFaceTB/SmolVLM-Instruct" # compact VLM for frame description
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"   # 384-dim outputs
SUMMARIZATION_MODEL = "facebook/bart-large-cnn"  # summarizer

# ----------------------------------------------------------------------

print(f"Using device: {DEVICE}")
print("[INFO] Starting video search system...")

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class Frame:
    frame_id: int
    timestamp: float
    description: str

@dataclass
class SearchResult:
    frame_id: int
    timestamp: float
    description: str
    similarity: float

@dataclass
class SearchResponse:
    query: str
    total_results: int
    results: List[SearchResult]
    summary: Optional[str] = None

# ============================================================================
# Database
# ============================================================================

class VideoDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init()

    def _init(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS frames (
                        frame_id INTEGER PRIMARY KEY,
                        timestamp REAL,
                        description TEXT
                    )
                """)
                conn.commit()
            print(f"[INFO] Database initialized: {self.db_path}")
        except Exception as e:
            print(f"[ERROR] Database init failed: {e}")
            raise

    def save(self, frame_id: int, timestamp: float, description: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO frames VALUES (?, ?, ?)",
                (frame_id, timestamp, description)
            )
            conn.commit()

    def get(self, frame_id: int) -> Optional[Frame]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT frame_id, timestamp, description FROM frames WHERE frame_id=?",
                (frame_id,)
            ).fetchone()
        return Frame(*row) if row else None

    def get_all(self) -> List[Frame]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT frame_id, timestamp, description FROM frames ORDER BY timestamp"
            ).fetchall()
        return [Frame(*row) for row in rows]

# ============================================================================
# FAISS Index (now 1152‑dim for three concatenated embeddings)
# ============================================================================

EMBEDDING_DIM = 384          # single embedding dimension
COMBINED_DIM = EMBEDDING_DIM * 3   # [objects, caption, motion]

class FAISSIdx:
    def __init__(self, faiss_path: str, map_path: str):
        self.faiss_path = faiss_path
        self.map_path = map_path
        self.map = {}
        self._load_or_create()

    def _load_or_create(self):
        try:
            if Path(self.faiss_path).exists():
                print(f"[INFO] Loading FAISS index from {self.faiss_path}")
                self.index = faiss.read_index(self.faiss_path)
                # verify dimension is COMBINED_DIM; if not, recreate
                if self.index.d != COMBINED_DIM:
                    print("[WARN] Existing FAISS index has wrong dimension, recreating...")
                    self.index = faiss.IndexFlatIP(COMBINED_DIM)
                    self.map = {}
                else:
                    with open(self.map_path) as f:
                        self.map = {int(k): v for k, v in json.load(f).items()}
                    print(f"[INFO] Loaded {len(self.map)} frame mappings")
            else:
                print(f"[INFO] Creating new FAISS index (dim={COMBINED_DIM})")
                self.index = faiss.IndexFlatIP(COMBINED_DIM)
        except Exception as e:
            print(f"[ERROR] FAISS init failed: {e}")
            raise

    def add(self, frame_id: int, embedding: np.ndarray):
        # embedding already normalized
        emb = embedding.astype(np.float32).reshape(1, -1)
        self.index.add(emb)
        self.map[len(self.map)] = frame_id

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Tuple[int, float]]:
        if len(self.map) == 0:
            return []
        emb = query_embedding.astype(np.float32).reshape(1, -1)
        distances, indices = self.index.search(emb, min(top_k, len(self.map)))
        # distances are inner products (cosine sim after normalization), convert to 0-100%
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:
                continue
            fid = self.map[int(idx)]
            sim = round(float(dist) * 100, 1)
            results.append((fid, sim))
        return results

    def save(self):
        try:
            faiss.write_index(self.index, self.faiss_path)
            with open(self.map_path, "w") as f:
                json.dump(self.map, f)
            print(f"[INFO] Saved FAISS index with {len(self.map)} frames")
        except Exception as e:
            print(f"[ERROR] Failed to save FAISS index: {e}")
            raise

# ============================================================================
# Multimodal Frame Encoder (YOLO + VLM + Optical Flow)
# ============================================================================

class FrameEncoder:
    def __init__(self, use_vlm: bool = True):
        print("[INFO] Loading embedding model...")
        self.emb_model = SentenceTransformer(EMBEDDING_MODEL, device=DEVICE)
        
        print("[INFO] Loading YOLO model...")
        self.yolo_model = YOLO("yolov8n.pt")
        if DEVICE == "cuda":
            self.yolo_model = self.yolo_model.to(DEVICE)
        
        self.vlm = None
        self.vlm_proc = None

        if use_vlm:
            print("[INFO] Loading VLM model (this may take a minute)...")
            try:
                self.vlm = AutoModelForVision2Seq.from_pretrained(
                    VLM_MODEL,
                    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
                    device_map="auto",
                    trust_remote_code=True
                )
                self.vlm_proc = AutoProcessor.from_pretrained(VLM_MODEL)
                print("[INFO] VLM loaded successfully")
            except Exception as e:
                print(f"[WARN] Failed to load VLM: {e}, using fallback")
                self.vlm = None
        print("[INFO] FrameEncoder initialized")

    def detect_objects(self, frame_bgr: np.ndarray) -> List[str]:
        """Run YOLOv8 on BGR frame, return sorted unique class names."""
        try:
            results = self.yolo_model(frame_bgr, verbose=False)
            objects = set()
            for r in results:
                for cls_id in r.boxes.cls:
                    objects.add(self.yolo_model.names[int(cls_id)])
            return sorted(objects)
        except Exception as e:
            print(f"[WARN] Object detection failed: {e}")
            return []

    def motion_vector(self, frame_bgr: np.ndarray,
                      prev_frame_bgr: Optional[np.ndarray]) -> Tuple[float, Optional[float]]:
        """
        Compute average optical flow magnitude and dominant direction.
        Returns (avg_magnitude, angle_degrees) where angle is None if no prev frame.
        """
        try:
            if prev_frame_bgr is None:
                return 0.0, None
            gray1 = cv2.cvtColor(prev_frame_bgr, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(gray1, gray2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            avg_mag = float(np.mean(mag))
            # dominant direction from angle histogram
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
            # convert angle to cardinal direction
            dirs = ["rightward", "down-right", "downward", "down-left",
                    "leftward", "up-left", "upward", "up-right"]
            idx = int((angle_deg + 22.5) // 45) % 8
            direction = dirs[idx]
            return f"{speed} {direction}"
        else:
            return speed

    def describe_vlm(self, frame_rgb: np.ndarray, object_hint: str = "") -> str:
        """Use VLM (or fallback) to describe the frame."""
        if self.vlm is not None:
            try:
                img = Image.fromarray(frame_rgb)
                prompt_text = "Describe this image briefly, including actions and spatial relations."
                if object_hint:
                    prompt_text += f" Detected objects: {object_hint}."
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image"},
                            {"type": "text", "text": prompt_text}
                        ]
                    }
                ]
                prompt = self.vlm_proc.apply_chat_template(messages, add_generation_prompt=True)
                inputs = self.vlm_proc(text=prompt, images=img, return_tensors="pt").to(DEVICE)
                with torch.no_grad():
                    out = self.vlm.generate(**inputs, max_new_tokens=80, do_sample=False)
                out = out[:, inputs["input_ids"].shape[1]:]
                return self.vlm_proc.batch_decode(out, skip_special_tokens=True)[0].strip()
            except Exception as e:
                print(f"[WARN] VLM inference failed: {e}")
                return self._fallback(frame_rgb)
        return self._fallback(frame_rgb)

    def _fallback(self, frame_rgb: np.ndarray) -> str:
        try:
            gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            brightness = np.mean(gray)
            light = "bright" if brightness > 150 else "dim" if brightness < 100 else "normal"
            edges = cv2.Canny(gray, 100, 200)
            detail = "detailed" if np.sum(edges > 0) / edges.size > 0.05 else "simple"
            return f"A {light}, {detail} scene."
        except Exception as e:
            print(f"[WARN] Fallback description failed: {e}")
            return "Frame description unavailable."

    def encode_frame(self, frame_bgr: np.ndarray,
                     prev_frame_bgr: Optional[np.ndarray] = None) -> Tuple[np.ndarray, str]:
        """
        Process frame and return (combined embedding, full description text).
        embedding is L2‑normalized 1152‑dim vector.
        """
        try:
            # 1. Objects
            objects = self.detect_objects(frame_bgr)
            obj_text = "Objects: " + ", ".join(objects) if objects else "no objects"

            # 2. VLM caption (use frame converted to RGB)
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            desc_text = self.describe_vlm(frame_rgb, object_hint=obj_text)

            # 3. Motion
            avg_mag, angle = self.motion_vector(frame_bgr, prev_frame_bgr)
            motion_text = "Motion: " + self.motion_to_text(avg_mag, angle)

            # Embed each textual description
            emb_obj = self.emb_model.encode(obj_text, convert_to_numpy=True)
            emb_desc = self.emb_model.encode(desc_text, convert_to_numpy=True)
            emb_mot = self.emb_model.encode(motion_text, convert_to_numpy=True)

            # Concatenate and normalize
            combined = np.concatenate([emb_obj, emb_desc, emb_mot])
            norm = np.linalg.norm(combined) + 1e-8
            combined = combined / norm

            full_desc = f"{desc_text} | {obj_text} | {motion_text}"
            return combined.astype(np.float32), full_desc
        except Exception as e:
            print(f"[ERROR] Frame encoding failed: {e}")
            raise

    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode a text query into the same 1152‑dim space.
        Uses the query for objects and description parts; motion is neutral.
        """
        try:
            # Object part – expand query to match object naming
            obj_query = f"Objects: {query}"
            emb_obj = self.emb_model.encode(obj_query, convert_to_numpy=True)

            # Description part – original query
            emb_desc = self.emb_model.encode(query, convert_to_numpy=True)

            # Motion part – unknown
            emb_mot = self.emb_model.encode("Motion: unknown", convert_to_numpy=True)

            combined = np.concatenate([emb_obj, emb_desc, emb_mot])
            norm = np.linalg.norm(combined) + 1e-8
            return (combined / norm).astype(np.float32)
        except Exception as e:
            print(f"[ERROR] Query encoding failed: {e}")
            raise

# ============================================================================
# Summarizer (unchanged)
# ============================================================================

class Summarizer:
    def __init__(self):
        print("[INFO] Loading summarization model...")
        try:
            self.pipe = pipeline(
                "summarization",
                model=SUMMARIZATION_MODEL,
                device=0 if DEVICE == "cuda" else -1
            )
            print("[INFO] Summarizer loaded")
        except Exception as e:
            print(f"[WARN] Failed to load summarizer: {e}")
            self.pipe = None

    def summarize(self, descriptions: List[str], max_length: int = 100, min_length: int = 30) -> str:
        if not descriptions or self.pipe is None:
            return ""
        try:
            text = " ".join(descriptions)
            if len(text.split()) < 20:
                return text
            result = self.pipe(text, max_length=max_length, min_length=min_length, do_sample=False)
            return result[0]['summary_text']
        except Exception as e:
            print(f"[WARN] Summarization failed: {e}")
            return " ".join(descriptions[:2])

# ============================================================================
# Main Video Search System
# ============================================================================

class VideoSearch:
    def __init__(self, db_path: str = "video.db", faiss_path: str = "video.faiss",
                 map_path: str = "video.json"):
        print("[INFO] Initializing VideoSearch...")
        self.db = VideoDB(db_path)
        self.faiss = FAISSIdx(faiss_path, map_path)
        self.encoder = FrameEncoder()
        self.summarizer = Summarizer()
        print("[INFO] VideoSearch ready")

    def index_video(self, video_path: str, sampling: int = 16) -> int:
        """Index a video file or webcam stream. Returns number of indexed frames."""
        print(f"[INFO] Opening video: {video_path}")
        
        if video_path == "0":
            print("[INFO] Opening webcam...")
            cap = cv2.VideoCapture(0)
        else:
            # Check if file exists
            if not Path(video_path).exists():
                print(f"[ERROR] Video file not found: {video_path}")
                print(f"[INFO] Current directory: {Path.cwd()}")
                print(f"[INFO] Absolute path: {Path(video_path).absolute()}")
                return 0
            cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"[ERROR] Cannot open video: {video_path}")
            return 0

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"[INFO] FPS: {fps:.1f} | Total frames: {total_frames}")
        print(f"[INFO] Sampling: every {sampling}-th frame")

        indexed = 0
        sampled = 0
        start_time = time.time()
        prev_frame = None

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("[INFO] End of video reached")
                    break
                
                indexed += 1
                
                if indexed % sampling != 0:
                    prev_frame = frame  # still track previous frame for motion
                    continue

                sampled += 1
                timestamp = (indexed / fps) if fps > 0 else time.time() - start_time

                try:
                    t0 = time.time()
                    embedding, full_desc = self.encoder.encode_frame(frame, prev_frame)
                    elapsed = time.time() - t0

                    self.db.save(indexed, timestamp, full_desc)
                    self.faiss.add(indexed, embedding)

                    print(f"[{sampled}] Frame {indexed}/{total_frames} | {full_desc[:80]}... ({elapsed:.2f}s)")
                except Exception as e:
                    print(f"[ERROR] Failed to encode frame {indexed}: {e}")
                    continue

                prev_frame = frame

        except KeyboardInterrupt:
            print("[INFO] Indexing interrupted by user")
        except Exception as e:
            print(f"[ERROR] Unexpected error during indexing: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cap.release()

        self.faiss.save()
        print(f"\n[SUCCESS] Indexed {sampled} frames (from {indexed} total)")
        return sampled

    def search(self, query: str, top_k: int = 10, summarize: bool = True) -> dict:
        print(f"[INFO] Searching for: '{query}'")
        frames = self.db.get_all()
        if not frames:
            print("[WARN] No indexed frames found")
            return {"query": query, "total_results": 0, "results": [], "summary": None}

        print(f"[INFO] Searching {len(frames)} frames...")
        # Encoded query vector
        q_emb = self.encoder.encode_query(query)

        # FAISS search
        matches = self.faiss.search(q_emb, top_k)

        results = []
        descriptions = []
        for fid, sim in matches:
            frame = self.db.get(fid)
            if frame:
                results.append(SearchResult(
                    frame.frame_id,
                    frame.timestamp,
                    frame.description,
                    sim
                ))
                descriptions.append(frame.description)

        summary = None
        if summarize and descriptions:
            print("[INFO] Generating summary...")
            summary = self.summarizer.summarize(descriptions)

        print(f"[SUCCESS] Found {len(results)} results")
        return {
            "query": query,
            "total_results": len(results),
            "results": [asdict(r) for r in results],
            "summary": summary,
            "note": "Similarity scores are percentages (0-100). Scores above 20% indicate potential matches."
        }

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Multimodal Video Search: YOLO + VLM + Motion")
    subparsers = parser.add_subparsers(dest="cmd")

    # Index command
    idx = subparsers.add_parser("index", help="Index a video file or webcam")
    idx.add_argument("source", help="Video file path or '0' for webcam")
    idx.add_argument("--sampling", type=int, default=16, help="Index every N-th frame")

    # Search command
    srch = subparsers.add_parser("search", help="Search indexed video")
    srch.add_argument("query", help="Text query")
    srch.add_argument("--top-k", type=int, default=10, help="Number of results")
    srch.add_argument("--no-summary", action="store_true", help="Disable summarization")
    srch.add_argument("--output", help="Save JSON output to file")

    args = parser.parse_args()

    try:
        vs = VideoSearch()

        if args.cmd == "index":
            print(f"\n{'='*60}")
            print(f"Starting indexing: {args.source}")
            print(f"{'='*60}\n")
            vs.index_video(args.source, args.sampling)
        elif args.cmd == "search":
            print(f"\n{'='*60}")
            print(f"Starting search: {args.query}")
            print(f"{'='*60}\n")
            result = vs.search(args.query, args.top_k, not args.no_summary)
            print(json.dumps(result, indent=2))
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"\n[INFO] Saved to {args.output}")
        else:
            parser.print_help()
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()