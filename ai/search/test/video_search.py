import json
import sqlite3
import argparse
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional

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

VLM_MODEL = "HuggingFaceTB/SmolVLM-Instruct" 
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2" # Fast and good for semantic search
SUMMARIZATION_MODEL = "facebook/bart-large-cnn"
yolo_model = YOLO("yolov8n.pt").to(DEVICE)

# ----------------------------------------------------------------------

print(f"Device: {DEVICE}")


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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS frames (
                    frame_id INTEGER PRIMARY KEY,
                    timestamp REAL,
                    description TEXT
                )
            """)
            conn.commit()

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
# FAISS Index
# ============================================================================

class FAISSIdx:
    def __init__(self, faiss_path: str, map_path: str):
        self.faiss_path = faiss_path
        self.map_path = map_path
        self.map = {}
        self._load_or_create()

    def _load_or_create(self):
        if Path(self.faiss_path).exists():
            self.index = faiss.read_index(self.faiss_path)
            with open(self.map_path) as f:
                self.map = {int(k): v for k, v in json.load(f).items()}
        else:
            self.index = faiss.IndexFlatIP(384)

    def add(self, frame_id: int, embedding: np.ndarray):
        emb = embedding / (np.linalg.norm(embedding) + 1e-8)
        self.index.add(np.array([emb], dtype=np.float32))
        self.map[len(self.map)] = frame_id

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[tuple]:
        if len(self.map) == 0:
            return []
        emb = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        distances, indices = self.index.search(np.array([emb], dtype=np.float32), min(top_k, len(self.map)))
        # Convert cosine similarity (0-1) to percentage (0-100)
        return [(self.map[int(idx)], round(float(dist) * 100, 1)) for idx, dist in zip(indices[0], distances[0])]

    def save(self):
        faiss.write_index(self.index, self.faiss_path)
        with open(self.map_path, "w") as f:
            json.dump(self.map, f)


# ============================================================================
# Frame Describer
# ============================================================================

class Describer:
    def __init__(self, use_vlm: bool = True):
        self.emb_model = SentenceTransformer(EMBEDDING_MODEL, device=DEVICE)
        self.vlm = None
        self.vlm_proc = None
        
        if use_vlm:
            try:
                self.vlm = AutoModelForVision2Seq.from_pretrained(
                    VLM_MODEL,
                    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
                    device_map="auto",
                    trust_remote_code=True
                )
                self.vlm_proc = AutoProcessor.from_pretrained(VLM_MODEL)
            except Exception as e:
                print(f"[WARN] VLM failed: {e}, using fallback")
                self.vlm = None

    def describe(self, frame_rgb: np.ndarray) -> str:
        if self.vlm:
            try:
                img = Image.fromarray(frame_rgb)
                msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Describe this image briefly."}]}]
                prompt = self.vlm_proc.apply_chat_template(msgs, add_generation_prompt=True)
                inputs = self.vlm_proc(text=prompt, images=img, return_tensors="pt").to(DEVICE)
                with torch.no_grad():
                    out = self.vlm.generate(**inputs, max_new_tokens=60, do_sample=False)
                out = out[:, inputs["input_ids"].shape[1]:]
                return self.vlm_proc.batch_decode(out, skip_special_tokens=True)[0].strip()
            except Exception as e:
                print(f"[ERROR] VLM: {e}")
                return self._fallback(frame_rgb)
        return self._fallback(frame_rgb)

    def _fallback(self, frame_rgb: np.ndarray) -> str:
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        brightness = np.mean(gray)
        light = "bright" if brightness > 150 else "dim" if brightness < 100 else "normal"
        edges = cv2.Canny(gray, 100, 200)
        detail = "detailed" if np.sum(edges > 0) / edges.size > 0.05 else "simple"
        return f"A {light}, {detail} scene."

    def embed(self, text: str) -> np.ndarray:
        return self.emb_model.encode(text, convert_to_numpy=True)


# ============================================================================
# Summarizer
# ============================================================================

class Summarizer:
    def __init__(self):
        self.pipe = pipeline("summarization", model=SUMMARIZATION_MODEL, device=0 if DEVICE == "cuda" else -1)

    def summarize(self, descriptions: List[str], max_length: int = 100, min_length: int = 30) -> str:
        if not descriptions:
            return ""
        
        text = " ".join(descriptions)
        if len(text.split()) < 20:
            return text
        
        try:
            result = self.pipe(text, max_length=max_length, min_length=min_length, do_sample=False)
            return result[0]['summary_text']
        except Exception as e:
            print(f"[ERROR] Summarization: {e}")
            return text[:200]


# ============================================================================

class VideoSearch:
    def __init__(self, db_path: str = "video.db", faiss_path: str = "video.faiss", map_path: str = "video.json"):
        self.db = VideoDB(db_path)
        self.faiss = FAISSIdx(faiss_path, map_path)
        self.describer = Describer()
        self.summarizer = Summarizer()

    def index_video(self, video_path: str, sampling: int = 16) -> int:
        """Index video and return number of indexed frames."""
        cap = cv2.VideoCapture(0 if video_path == "0" else video_path)
        if not cap.isOpened():
            print(f"Error: Cannot open {video_path}")
            return 0

        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"FPS: {fps:.1f} | Frames: {total}")

        indexed = 0
        start = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            indexed += 1
            if indexed % sampling != 0:
                continue

            ts = time.time() - start
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            t0 = time.time()
            desc = self.describer.describe(rgb)
            emb = self.describer.embed(desc)
            elapsed = time.time() - t0

            self.db.save(indexed, ts, desc)
            self.faiss.add(indexed, emb)

            print(f"[{indexed}/{total}] {desc[:50]}... ({elapsed:.1f}s)")

        cap.release()
        self.faiss.save()
        print(f"\nIndexed {int(indexed/sampling)} frames")
        return int(indexed / sampling)

    def _expand_query(self, query: str) -> str:
        """Expand query with context for better semantic matching."""
        # Common context additions
        expansions = [
            query,
            f"scene with {query}",
            f"image showing {query}",
            f"video of {query}",
            f"{query} in the frame"
        ]
        # Embed all variations and average them for richer representation
        embeddings = [self.describer.embed(exp) for exp in expansions]
        return query  # Return original, but we'll average embeddings

    def search(self, query: str, top_k: int = 10, summarize: bool = True) -> dict:
        """Search and optionally summarize results. Returns JSON-ready dict."""
        frames = self.db.get_all()
        if not frames:
            return {"query": query, "total_results": 0, "results": [], "summary": None}

        # Search with query
        emb = self.describer.embed(query)
        matches = self.faiss.search(emb, top_k)

        results = []
        descriptions = []
        for fid, sim in matches:
            frame = self.db.get(fid)
            if frame:
                results.append(SearchResult(frame.frame_id, frame.timestamp, frame.description, sim))
                descriptions.append(frame.description)

        # Summarize if requested
        summary = None
        if summarize and descriptions:
            summary = self.summarizer.summarize(descriptions)

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
    parser = argparse.ArgumentParser(description="Video Search with Summarization")
    subparsers = parser.add_subparsers(dest="cmd")

    # Index command
    idx = subparsers.add_parser("index", help="Index video")
    idx.add_argument("source", help="Video file or 0 for webcam")
    idx.add_argument("--sampling", type=int, default=16, help="Sample every N frames")

    # Search command
    srch = subparsers.add_parser("search", help="Search indexed video")
    srch.add_argument("query", help="Search query")
    srch.add_argument("--top-k", type=int, default=10, help="Top results")
    srch.add_argument("--no-summary", action="store_true", help="Skip summarization")
    srch.add_argument("--output", help="Save JSON to file")

    args = parser.parse_args()
    vs = VideoSearch()

    if args.cmd == "index":
        vs.index_video(args.source, args.sampling)
    elif args.cmd == "search":
        result = vs.search(args.query, args.top_k, not args.no_summary)
        
        # Print JSON
        print(json.dumps(result, indent=2))
        
        # Save if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\nSaved to {args.output}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()