import os
import csv
import json
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from minio import Minio
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from search.models.search import IndexedVideo, VideoFrame

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
COMBINED_DIM = EMBEDDING_DIM * 3

# ----------------------------------------------------------------------
# Query Encoder (Matches offline frame indexing dimension of 1152)
# ----------------------------------------------------------------------

class QueryEncoder:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        import torch
        from sentence_transformers import SentenceTransformer
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[INFO] Loading SentenceTransformer query encoder model: {EMBEDDING_MODEL} on {device}...")
        self.emb_model = SentenceTransformer(EMBEDDING_MODEL, device=device)
        print("[INFO] SentenceTransformer model loaded successfully.")

    def encode(self, query: str):
        import numpy as np
        obj_query = f"Objects: {query}"
        mot_query = "Motion: unknown"

        emb_obj = self.emb_model.encode(obj_query, convert_to_numpy=True)
        emb_desc = self.emb_model.encode(query, convert_to_numpy=True)
        emb_mot = self.emb_model.encode(mot_query, convert_to_numpy=True)

        combined = np.concatenate([emb_obj, emb_desc, emb_mot])
        norm = np.linalg.norm(combined) + 1e-8
        return (combined / norm).astype(np.float32)

# ----------------------------------------------------------------------
# LLM Reasoner for CPU-based local visual query summarization
# ----------------------------------------------------------------------

class LLMReasoner:
    _instance = None

    @classmethod
    def get_instance(cls, model_name="Qwen/Qwen2.5-0.5B-Instruct"):
        if cls._instance is None:
            cls._instance = cls(model_name)
        return cls._instance

    def __init__(self, model_name="Qwen/Qwen2.5-0.5B-Instruct"):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        print(f"[INFO] Loading local CPU LLM for reasoning: {model_name}...")
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
        print("[INFO] Local CPU LLM loaded successfully.")

    def answer(self, query: str, contexts: List[str], max_new_tokens=256) -> str:
        import torch
        fused_context = "\n".join([f"- {ctx}" for ctx in contexts])
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Rawi-Vision Search AI, a security intelligence assistant. "
                    "Analyze the provided surveillance visual metadata context and timeline. "
                    "Synthesize a clear, concise, and direct description of the event matching "
                    "the query. Keep the response factual, short, and objective. "
                    "Refer to subjects by their real-time identities and tracks if present."
                )
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nMetadata Context:\n{fused_context}\n\nAnswer:"
            }
        ]
        
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id
            )
        
        input_length = inputs["input_ids"].shape[1]
        answer = self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
        return answer.strip() if answer else "No reasoning generated."

# ----------------------------------------------------------------------
# Main Search Service wrapping postgres pgvector and MinIO access
# ----------------------------------------------------------------------

class SearchService:
    def __init__(self):
        # Initialize MinIO client
        minio_url = Config.MINIO_SERVER_URL.replace("http://", "").replace("https://", "")
        self.minio_client = Minio(
            minio_url,
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=False
        )

    def load_realtime_events(self) -> List[dict]:
        """Loads events from the events.csv file generated by fusion.py"""
        paths = [
            Path("events.csv"),
            Path("backend/events.csv"),
            Path("../events.csv"),
            Path("../../events.csv")
        ]
        for p in paths:
            if p.exists():
                try:
                    events = []
                    with open(p, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            events.append(row)
                    print(f"[INFO] Successfully loaded {len(events)} real-time biometric events from {p}")
                    return events
                except Exception as e:
                    print(f"[WARN] Failed to read events.csv at {p}: {e}")
        return []

    async def search(self, db: AsyncSession, video_id: uuid.UUID, query: str, top_k: int = 10, use_llm: bool = True) -> dict:
        # Encode query using cached/lazy QueryEncoder
        encoder = QueryEncoder.get_instance()
        query_vector = encoder.encode(query).tolist()

        # Perform pgvector cosine similarity search using SQLAlchemy
        # Vector cosine distance is (1 - CosineSimilarity)
        stmt = (
            select(VideoFrame, (1 - VideoFrame.embedding.cosine_distance(query_vector)).label("similarity"))
            .filter(VideoFrame.video_id == video_id)
            .order_by("similarity")
            .limit(top_k)
        )
        
        result = await db.execute(stmt)
        rows = result.all()

        # Load events.csv to map identities
        rt_events = self.load_realtime_events()
        query_words_lower = [w.strip(".,?!()\"'").lower() for w in query.split()]
        
        # Track names or track IDs matching query
        matched_rt_tracks = set()
        for row in rt_events:
            row_name = row.get("name", "").strip().lower()
            if row_name and row_name != "unknown":
                if any(word == row_name or row_name in word for word in query_words_lower):
                    track_id_str = row.get("track_id", "")
                    if track_id_str:
                        matched_rt_tracks.add(int(track_id_str))

        results = []
        descriptions = []
        active_track_ids = set()

        for frame_row, similarity_score in rows:
            # Convert decimal similarity to percentage
            sim = round(float(similarity_score) * 100, 1)
            
            frame_track_ids = []
            if frame_row.tracks:
                try:
                    frame_track_ids = [int(t) for t in frame_row.tracks.split(",") if t.strip()]
                except ValueError:
                    pass
            
            # Fuse with identity information from events.csv
            enriched_desc = frame_row.description
            active_names = []
            for t in frame_track_ids:
                active_track_ids.add(t)
                for row in rt_events:
                    if row.get("track_id") == str(t) and row.get("name") and row.get("name").lower() != "unknown":
                        active_names.append(f"{row.get('name')} (Track {t})")
                        break
            
            if active_names:
                enriched_desc = f"{frame_row.description} [Real-time Identity: {', '.join(active_names)}]"

            # Generate presigned MinIO video clip URL
            clip_object_name = f"extracted_clips/{video_id}/clip_frame_{frame_row.frame_number}_{frame_row.timestamp_offset:.2f}s.mp4"
            clip_url = None
            try:
                # Expiry set to 1 hour
                clip_url = self.minio_client.presigned_get_object(
                    bucket_name="extracted-search-clips",
                    object_name=clip_object_name,
                    expires=3600
                )
            except Exception as e:
                print(f"[WARN] MinIO presigned URL error: {e}")

            results.append({
                "frame_id": frame_row.frame_number,
                "timestamp": round(frame_row.timestamp_offset, 2),
                "similarity": sim,
                "description": enriched_desc,
                "clip_url": clip_url,
                "track_ids": frame_track_ids
            })
            descriptions.append(enriched_desc)

        # Build Re-ID timeline of when each track ID was seen throughout the video
        reid_tracks = {}
        if active_track_ids:
            # Query all frames to trace the timeline of active track IDs
            all_frames_stmt = select(VideoFrame).filter(VideoFrame.video_id == video_id).order_by(VideoFrame.timestamp_offset)
            all_frames_result = await db.execute(all_frames_stmt)
            all_frames = all_frames_result.scalars().all()

            for track_id in active_track_ids:
                appearances = []
                for f in all_frames:
                    if f.tracks:
                        f_track_ids = [int(t) for t in f.tracks.split(",") if t.strip()]
                        if track_id in f_track_ids:
                            appearances.append({
                                "frame_id": f.frame_number,
                                "timestamp": round(f.timestamp_offset, 2)
                            })
                reid_tracks[f"Track {track_id}"] = appearances

        # Generate timeline tracking summary context
        tracking_context_str = ""
        if reid_tracks:
            tracking_context_str = "\nSubject Tracking & Re-ID Timelines:\n"
            for track_name, apps in reid_tracks.items():
                timestamps_str = ", ".join([f"{a['timestamp']}s" for a in apps])
                tracking_context_str += f"- {track_name} was detected at: {timestamps_str}\n"

        # Local CPU LLM RAG Reasoning
        llm_answer = None
        if use_llm and descriptions:
            try:
                # Inject tracking details
                combined_descriptions = list(descriptions)
                if tracking_context_str:
                    combined_descriptions.append(tracking_context_str)
                
                llm = LLMReasoner.get_instance()
                llm_answer = llm.answer(query, combined_descriptions)
            except Exception as e:
                print(f"[WARN] Local CPU LLM execution failed: {e}")
                llm_answer = "Local LLM reasoning unavailable."

        return {
            "query": query,
            "total_results": len(results),
            "results": results,
            "reid_tracks": reid_tracks,
            "llm_answer": llm_answer
        }
