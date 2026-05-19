#!/usr/bin/env python3

import json
import sqlite3
import argparse
import csv
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import torch

# Optional LLM (SmolLM2 – works without bitsandbytes)
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- Fixed constants (must match offline indexing) ---
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
COMBINED_DIM = EMBEDDING_DIM * 3

# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------

@dataclass
class Frame:
    frame_id: int
    timestamp: float
    description: str
    tracks: Optional[str] = ""

@dataclass
class SearchResult:
    frame_id: int
    timestamp: float
    description: str
    similarity: float
    clip_path: Optional[str] = None
    track_ids: Optional[List[int]] = None

@dataclass
class SearchResponse:
    query: str
    total_results: int
    results: List[SearchResult]
    summary: Optional[str] = None
    llm_answer: Optional[str] = None

# ----------------------------------------------------------------------
# Database (read‑only)
# ----------------------------------------------------------------------

class VideoDB:
    def __init__(self, db_path: str):
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        self.db_path = db_path

    def get(self, frame_id: int) -> Optional[Frame]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(frames)")
            cols = [c[1] for c in cursor.fetchall()]
            
            if "tracks" in cols:
                row = conn.execute(
                    "SELECT frame_id, timestamp, description, tracks FROM frames WHERE frame_id=?",
                    (frame_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT frame_id, timestamp, description FROM frames WHERE frame_id=?",
                    (frame_id,)
                ).fetchone()
        
        if not row:
            return None
        if len(row) == 4:
            return Frame(row[0], row[1], row[2], row[3])
        return Frame(row[0], row[1], row[2], "")

    def get_all(self) -> List[Frame]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(frames)")
            cols = [c[1] for c in cursor.fetchall()]
            
            if "tracks" in cols:
                rows = conn.execute(
                    "SELECT frame_id, timestamp, description, tracks FROM frames ORDER BY timestamp"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT frame_id, timestamp, description FROM frames ORDER BY timestamp"
                ).fetchall()
                
        results = []
        for r in rows:
            if len(r) == 4:
                results.append(Frame(r[0], r[1], r[2], r[3]))
            else:
                results.append(Frame(r[0], r[1], r[2], ""))
        return results

# ----------------------------------------------------------------------
# FAISS Index (read‑only)
# ----------------------------------------------------------------------

class FAISSIdx:
    def __init__(self, faiss_path: str, map_path: str):
        if not Path(faiss_path).exists():
            raise FileNotFoundError(f"FAISS index not found: {faiss_path}")
        print(f"[INFO] Loading FAISS index from {faiss_path}")
        self.index = faiss.read_index(faiss_path)
        if self.index.d != COMBINED_DIM:
            raise ValueError("FAISS index dimension mismatch")
        with open(map_path) as f:
            self.map = {int(k): v for k, v in json.load(f).items()}
        print(f"[INFO] Loaded {len(self.map)} frame mappings")

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Tuple[int, float]]:
        if len(self.map) == 0:
            return []
        emb = query_embedding.astype(np.float32).reshape(1, -1)
        distances, indices = self.index.search(emb, min(top_k, len(self.map)))
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:
                continue
            fid = self.map[int(idx)]
            sim = round(float(dist) * 100, 1)
            results.append((fid, sim))
        return results

# ----------------------------------------------------------------------
# Lightweight Query Encoder (no YOLO / VLM needed)
# ----------------------------------------------------------------------

class QueryEncoder:
    def __init__(self):
        self.emb_model = SentenceTransformer(EMBEDDING_MODEL, device=DEVICE)

    def encode(self, query: str) -> np.ndarray:
        obj_query = f"Objects: {query}"
        mot_query = "Motion: unknown"

        emb_obj = self.emb_model.encode(obj_query, convert_to_numpy=True)
        emb_desc = self.emb_model.encode(query, convert_to_numpy=True)
        emb_mot = self.emb_model.encode(mot_query, convert_to_numpy=True)

        combined = np.concatenate([emb_obj, emb_desc, emb_mot])
        norm = np.linalg.norm(combined) + 1e-8
        return (combined / norm).astype(np.float32)

# ----------------------------------------------------------------------
# LLM reasoning layer – SmolLM2 (CPU‑only, no bitsandbytes, no warnings)
# ----------------------------------------------------------------------

class LLMReasoner:
    def __init__(self, model_name="HuggingFaceTB/SmolLM2-1.7B-Instruct"):
        if not LLM_AVAILABLE:
            raise ImportError("LLM dependencies not installed (transformers)")
        print(f"[INFO] Loading LLM {model_name} on CPU...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="cpu",
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            trust_remote_code=True
        )
        print("[INFO] LLM loaded")

    def answer(self, query: str, contexts: List[str], max_new_tokens=256) -> str:
        # Use SmolLM2's chat template
        context_str = "\n".join([f"- {ctx}" for ctx in contexts[:5]])
        
        # Detect if the query is a direct question or a descriptive search term
        q_lower = query.strip().lower()
        is_question = q_lower.endswith("?") or any(q_lower.startswith(w) for w in ["what", "who", "where", "when", "why", "how", "is", "are", "can", "do", "does", "did", "was", "were"])
        
        if is_question:
            messages = [
                {"role": "system", "content": "You are a strictly factual video intelligence assistant. Answer the Question based ONLY on the provided frame descriptions. Do not make up any facts."},
                {"role": "user", "content": f"Context (video frame descriptions):\n{context_str}\n\nQuestion: {query}"}
            ]
        else:
            messages = [
                {"role": "system", "content": "You are a helpful and factual video intelligence assistant. Analyze and summarize the behavior of the matching people in the video frames."},
                {"role": "user", "content": (
                    f"Context (video frame descriptions):\n{context_str}\n\n"
                    f"Query: {query}\n\n"
                    f"Task:\n"
                    f"1. Confirm if the item, color, person, or clothing in the Query is described in the Context.\n"
                    f"2. If NO, output exactly: 'No match was found.'\n"
                    f"3. If YES, write a 1-2 sentence detailed summary analyzing the behavior, appearance, clothing, and actions of the matching person/people (e.g. 'The person in the blue shirt is standing in the aisle looking at products on the shelves...')."
                )}
            ]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,          # deterministic greedy decoding
            pad_token_id=self.tokenizer.pad_token_id
        )
        input_length = inputs["input_ids"].shape[1]
        answer = self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
        return answer.strip() if answer else "No answer generated."

# ----------------------------------------------------------------------
# Search Service
# ----------------------------------------------------------------------

class VideoSearchService:
    def __init__(self, db_path="video.db", faiss_path="video.faiss",
                 map_path="video.json", use_llm=True, llm_model_name=None):
        # Resolve paths dynamically to handle execution from core/ or search/ root directory cleanly
        def get_fallback(filename: str) -> str:
            if Path(filename).exists():
                return filename
            # Check data/
            p_data = Path("data") / filename
            if p_data.exists():
                return str(p_data)
            # Check ../data/ (when running from core/ or test/)
            p_parent_data = Path(__file__).resolve().parent.parent / "data" / filename
            if p_parent_data.exists():
                return str(p_parent_data)
            # Check in current dir relative (e.g. if we are running in core)
            p_relative = Path(__file__).resolve().parent / filename
            if p_relative.exists():
                return str(p_relative)
            return filename

        resolved_db = get_fallback(db_path)
        resolved_faiss = get_fallback(faiss_path)
        resolved_map = get_fallback(map_path)

        self.db = VideoDB(resolved_db)
        self.faiss = FAISSIdx(resolved_faiss, resolved_map)
        self.encoder = QueryEncoder()

        self.llm = None
        if use_llm:
            try:
                model = llm_model_name or "HuggingFaceTB/SmolLM2-1.7B-Instruct"
                self.llm = LLMReasoner(model_name=model)
            except Exception as e:
                print(f"[WARN] Failed to load LLM: {e}")

    def load_realtime_events(self) -> List[dict]:
        paths = [
            Path("events.csv"),
            Path("data/events.csv"),
            Path("../data/events.csv"),
            Path(__file__).resolve().parent.parent / "data" / "events.csv",
            Path("../backend/events.csv"),
            Path("../../backend/events.csv"),
            Path("backend/events.csv"),
            Path("backend/camera_ingestion/ai/events.csv"),
            Path("../backend/camera_ingestion/ai/events.csv")
        ]
        for p in paths:
            if p.exists():
                try:
                    events = []
                    with open(p, "r") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            events.append(row)
                    print(f"[INFO] Successfully loaded {len(events)} real-time events from {p}")
                    return events
                except Exception as e:
                    print(f"[WARN] Failed to read events.csv at {p}: {e}")
        return []

    def extract_clip(self, video_path: str, timestamp: float, frame_id: int, 
                     duration: float = 6.0, output_dir: str = "extracted_clips") -> Optional[str]:
        try:
            import cv2
        except ImportError:
            print("[WARN] OpenCV (cv2) not available. Cannot extract video clips.")
            return None

        video_p = Path(video_path)
        if not video_p.exists():
            print(f"[WARN] Original video not found at {video_path}, skipping clip extraction.")
            return None

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        cap = cv2.VideoCapture(str(video_p))
        if not cap.isOpened():
            print(f"[WARN] Cannot open video for clip extraction: {video_path}")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0:
            fps = 30.0

        half_dur = duration / 2.0
        start_time = max(0.0, timestamp - half_dur)
        end_time = min(total_frames / fps, timestamp + half_dur)

        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)

        output_file = out_path / f"clip_frame_{frame_id}_{timestamp:.2f}s.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(str(output_file), fourcc, fps, (width, height))

        if not out_writer.isOpened():
            print(f"[WARN] Failed to open VideoWriter for {output_file}. Trying alternative XVID/AVI format...")
            output_file = out_path / f"clip_frame_{frame_id}_{timestamp:.2f}s.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out_writer = cv2.VideoWriter(str(output_file), fourcc, fps, (width, height))
            if not out_writer.isOpened():
                print(f"[ERROR] Alternative VideoWriter failed as well.")
                cap.release()
                return None

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame = start_frame
        
        while current_frame <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            out_writer.write(frame)
            current_frame += 1

        cap.release()
        out_writer.release()
        print(f"[INFO] Extracted clip for Frame {frame_id} at {timestamp:.2f}s -> {output_file}")
        return str(output_file)

    def search(self, query: str, top_k: int = 10, use_llm: bool = True,
               video_path: Optional[str] = None, extract_clips: bool = True,
               clip_duration: float = 6.0, clips_dir: str = "extracted_clips") -> dict:
        # Auto-detect video path if not explicitly provided and clip extraction is requested
        if extract_clips and not video_path:
            # Look in videos/ folder first
            videos_dir = Path("videos")
            video_files = []
            if videos_dir.exists() and videos_dir.is_dir():
                video_files = list(videos_dir.glob("*.mp4")) + list(videos_dir.glob("*.avi")) + list(videos_dir.glob("*.mkv"))
            if not video_files:
                # Look in current working directory
                video_files = list(Path(".").glob("*.mp4")) + list(Path(".").glob("*.avi"))
            
            if video_files:
                video_path = str(video_files[0])
                print(f"[INFO] Auto-detected video source for clipping: {video_path}")

        # Load real-time attendance events from events.csv
        rt_events = self.load_realtime_events()

        # Clean and tokenize query words to match against registered names in events.csv
        query_words_lower = [w.strip(".,?!()\"'").lower() for w in query.split()]
        matched_rt_tracks = set()
        matched_rt_names = set()
        for row in rt_events:
            row_name = row.get("name", "").strip().lower()
            if row_name and row_name != "unknown":
                if any(word == row_name or row_name in word for word in query_words_lower):
                    track_id_str = row.get("track_id", "")
                    if track_id_str:
                        matched_rt_tracks.add(int(track_id_str))
                        matched_rt_names.add(row.get("name"))

        query_emb = self.encoder.encode(query)
        matches = self.faiss.search(query_emb, top_k)

        # 1. Fetch matching frames first and enrich them with real-time identities
        matched_frames = []
        descriptions = []
        for fid, sim in matches:
            frame = self.db.get(fid)
            if frame:
                frame_track_ids = [int(t) for t in frame.tracks.split(",") if t.strip()] if getattr(frame, "tracks", None) else []
                is_name_match = any(t in matched_rt_tracks for t in frame_track_ids)
                
                # Fuse visual VLM description with real-time Face Recognition metadata
                enriched_desc = frame.description
                active_names = []
                for t in frame_track_ids:
                    for row in rt_events:
                        if row.get("track_id") == str(t) and row.get("name") and row.get("name").lower() != "unknown":
                            active_names.append(f"{row.get('name')} (Track {t})")
                            break
                if active_names:
                    enriched_desc = f"{frame.description} [Real-time Identity: {', '.join(active_names)}]"

                matched_frames.append((frame, sim, enriched_desc, is_name_match))
                descriptions.append(enriched_desc)

        # 2. Run generalized semantic check before executing clip extraction and LLM reasoning
        is_match = True
        llm_answer = None

        if use_llm and self.llm and descriptions:
            stopwords = {
                "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
                "in", "on", "at", "with", "of", "for", "by", "to", "from", "up", "down",
                "person", "someone", "people", "man", "woman", "guy", "girl", "child",
                "wearing", "wear", "wears", "dressed", "clothed", "attire",
                "thing", "things", "item", "items", "something", "anything", "nothing",
                "video", "frame", "description", "descriptions", "surveillance", "footage", "camera"
            }
            query_cleaned = query.lower().replace("-", " ")
            query_words = [w.strip(".,?!()\"'") for w in query_cleaned.split()]
            key_terms = [w for w in query_words if w and w not in stopwords and len(w) > 1]
            
            if key_terms:
                has_matching_term = False
                for desc in descriptions:
                    desc_lower = desc.lower()
                    for term in key_terms:
                        if term in desc_lower:
                            has_matching_term = True
                            break
                    if has_matching_term:
                        break
                
                # If a name match occurred in real-time events.csv, confirm semantic match
                if matched_rt_tracks:
                    has_matching_term = True

                if not has_matching_term:
                    is_match = False
                    llm_answer = "No match was found."

        results = []
        reid_tracks = {}
        
        # 3. Only extract clips and query the LLM if we confirmed a true match exists!
        if is_match:
            for frame, sim, enriched_desc, _ in matched_frames:
                clip_path = None
                if extract_clips and video_path:
                    clip_path = self.extract_clip(video_path, frame.timestamp, frame.frame_id, 
                                                 clip_duration, clips_dir)
                track_ids = [int(t) for t in frame.tracks.split(",") if t.strip()] if getattr(frame, "tracks", None) else []
                results.append(SearchResult(frame.frame_id, frame.timestamp,
                                            enriched_desc, sim, clip_path, track_ids))
            
            # Perform Multi-Subject Re-ID profiling
            active_track_ids = set()
            for r in results:
                if r.track_ids:
                    active_track_ids.update(r.track_ids)
            
            if active_track_ids:
                all_frames = self.db.get_all()
                for track_id in active_track_ids:
                    appearances = []
                    for f in all_frames:
                        if getattr(f, "tracks", None):
                            f_track_ids = [int(t) for t in f.tracks.split(",") if f.tracks.strip()]
                            if track_id in f_track_ids:
                                appearances.append({
                                    "frame_id": f.frame_id,
                                    "timestamp": round(f.timestamp, 2)
                                })
                    reid_tracks[f"Track {track_id}"] = appearances

            # If we have Re-ID track timelines, format them as structured context for LLM track analysis
            tracking_context_str = ""
            if reid_tracks:
                tracking_context_str = "\nSubject Tracking & Re-ID Timelines:\n"
                for track_name, apps in reid_tracks.items():
                    timestamps_str = ", ".join([f"{a['timestamp']}s" for a in apps])
                    tracking_context_str += f"- {track_name} was detected at: {timestamps_str}\n"

            if use_llm and self.llm and descriptions and llm_answer is None:
                try:
                    # Merge descriptive context and Re-ID tracking timeline context
                    combined_descriptions = list(descriptions)
                    if tracking_context_str:
                        combined_descriptions.append(tracking_context_str)
                    llm_answer = self.llm.answer(query, combined_descriptions)
                except Exception as e:
                    print(f"[WARN] LLM failed: {e}")
                    llm_answer = "LLM reasoning unavailable."

        # Filter real-time events to only return rows relevant to matching tracks or queried names
        filtered_rt_events = []
        active_track_ids_str = {str(t) for t in active_track_ids} if 'active_track_ids' in locals() else set()
        for row in rt_events:
            if row.get("track_id") in active_track_ids_str or any(word in row.get("name", "").lower() for word in query_words_lower):
                filtered_rt_events.append(row)

        return {
            "query": query,
            "total_results": len(results),
            "results": [asdict(r) for r in results],
            "reid_tracks": reid_tracks,
            "realtime_events": filtered_rt_events,
            "llm_answer": llm_answer,
            "note": "Similarity scores are percentages (0-100). Scores above 20% indicate potential matches."
        }

# ----------------------------------------------------------------------
# CLI (Single Run)
# ----------------------------------------------------------------------

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python online_search.py <query>")
        sys.exit(1)
    
    query = sys.argv[1]
    print(f"[INFO] Initializing video search for query: '{query}'...")
    
    # Initialize service with default smart parameters (use Qwen-0.5B for fast, highly accurate local CPU reasoning)
    service = VideoSearchService(
        db_path="video.db",
        faiss_path="video.faiss",
        map_path="video.json",
        use_llm=True,
        llm_model_name="Qwen/Qwen2.5-0.5B-Instruct"
    )
    
    # Search and automatically detect video, extract clips, and run LLM summarization
    result = service.search(
        query=query,
        top_k=10,
        use_llm=True,
        video_path=None,
        extract_clips=True,
        clip_duration=6.0,
        clips_dir="extracted_clips"
    )
    
    print("\n--- SEARCH RESULTS ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()