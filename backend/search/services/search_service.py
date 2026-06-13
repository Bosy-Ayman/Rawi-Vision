import os
import csv
import json
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from minio import Minio
from sqlalchemy import desc
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
        device = "cpu"
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

    def answer(self, query: str, contexts: List[str], max_new_tokens=120) -> str:
        import torch
        import re

        # Separate the tracking/timeline context from the visual frame descriptions
        visual_contexts = [c for c in contexts if "Subject Tracking" not in c]
        tracking_contexts = [c for c in contexts if "Subject Tracking" in c]

        # Use only the top 3 visual frame descriptions to avoid overloading the context window
        top_visual = visual_contexts[:3]
        
        # Format the context cleanly
        fused_visual = "\n".join([f"- {ctx}" for ctx in top_visual])
        fused_tracking = "\n".join(tracking_contexts) if tracking_contexts else ""

        # Step 1: Hybrid validation check to avoid hallucinations on false positives
        # Extract alphanumeric lowercase words from query
        query_words = set(re.findall(r'[a-zA-Z0-9]+', query.lower()))
        # Filter out common stopwords
        STOPWORDS = {
            'a', 'an', 'the', 'in', 'on', 'at', 'by', 'with', 'for', 'of', 'and', 'or', 'is', 'are', 'was', 'were', 
            'be', 'been', 'being', 'to', 'from', 'he', 'she', 'it', 'they', 'them', 'his', 'her', 'their', 'him', 
            'who', 'whom', 'what', 'which', 'whose', 'this', 'that', 'these', 'those', 'i', 'you', 'we', 'us'
        }
        content_words = {w for w in query_words if w not in STOPWORDS and len(w) > 1}
        
        # Check if any content word exists in contexts
        context_lower = fused_visual.lower() + " " + fused_tracking.lower()
        has_direct_word_match = False
        if content_words:
            context_words = set(re.findall(r'[a-zA-Z0-9]+', context_lower))
            if content_words.issubset(context_words):
                has_direct_word_match = True

        # If no direct keyword match, run Yes/No validation using LLM
        is_match = True
        if not has_direct_word_match:
            messages_val = [
                {"role": "system", "content": "You are an AI analyzing security descriptions."},
                {"role": "user", "content": f"Context:\n{fused_visual}\n\nQuestion: Does the Context contain any description, mention, or objects related to '{query}'? Reply with only 'Yes' or 'No'."}
            ]
            prompt_val = self.tokenizer.apply_chat_template(messages_val, tokenize=False, add_generation_prompt=True)
            inputs_val = self.tokenizer(prompt_val, return_tensors="pt", truncation=True, max_length=1024)
            inputs_val = {k: v.to(self.model.device) for k, v in inputs_val.items()}
            with torch.no_grad():
                outputs_val = self.model.generate(
                    **inputs_val,
                    max_new_tokens=5,
                    do_sample=False,
                    repetition_penalty=1.1,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            input_length_val = inputs_val["input_ids"].shape[1]
            val_answer = self.tokenizer.decode(outputs_val[0][input_length_val:], skip_special_tokens=True).strip()
            if val_answer.lower().startswith("no"):
                is_match = False

        if not is_match:
            return "No matching events or objects found in this video."

        # Step 2: Factual Summary Generation (Run only if validated as a match)
        system_content = (
            "You are a factual video metadata analyzer. You must report only what is explicitly present in the provided context. "
            "Do not speculate, guess, or assume activities (like stealing, theft, or crimes) unless they are explicitly stated. "
            "Write a concise 2-sentence factual summary of the event based ONLY on the context."
        )
        user_content = f"Visual Metadata Context:\n{fused_visual}\n"
        if fused_tracking:
            user_content += f"\nTracking Context:\n{fused_tracking}\n"
        user_content += f"\nQuestion: {query}"
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                repetition_penalty=1.1,
                no_repeat_ngram_size=4,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        input_length = inputs["input_ids"].shape[1]
        answer = self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
        answer = answer.strip()

        # Clean answer to keep only the main paragraph and strip trailing notes/rambling
        paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
        if paragraphs:
            answer = paragraphs[0]
            
        lines = [l.strip() for l in answer.split("\n") if l.strip()]
        if lines:
            answer = lines[0]

        # Strip common meta-cognitive rambling prefixes/suffixes
        for term in ["please note", "note:", "in conclusion", "explanation:"]:
            if term in answer.lower():
                idx = answer.lower().find(term)
                answer = answer[:idx].strip()

        # If the model echoed the prompt or generated garbage, return a clean fallback description
        if not answer or len(answer) < 15 or "Write a concise" in answer:
            return "Based on the visual search results, matched frames highlight scenes similar to your query."
        return answer

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

    async def search(self, db: AsyncSession, video_id: uuid.UUID, query: str, top_k: int = 10, use_llm: bool = True) -> Dict[str, Any]:
        import asyncio
        # Encode query using cached/lazy QueryEncoder
        encoder = QueryEncoder.get_instance()
        # Run synchronous text encoding in a separate thread
        query_vector_np = await asyncio.to_thread(encoder.encode, query)
        query_vector = query_vector_np.tolist()

        # Perform pgvector cosine similarity search using SQLAlchemy
        # Vector cosine distance is (1 - CosineSimilarity)
        stmt = (
            select(VideoFrame, (1 - VideoFrame.embedding.cosine_distance(query_vector)).label("similarity"))
            .filter(VideoFrame.video_id == video_id)
            .order_by(desc("similarity"))
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
        raw_descriptions_map = {}  # map frame_number to clean VLM desc
        active_track_ids = set()

        SIM_THRESHOLD = 35.0

        for frame_row, similarity_score in rows:
            # Convert decimal similarity to percentage
            sim = round(float(similarity_score) * 100, 1)
            
            # Skip matches that are below the similarity threshold
            if sim < SIM_THRESHOLD:
                continue
                
            frame_track_ids = []
            if frame_row.tracks:
                try:
                    frame_track_ids = [int(t) for t in frame_row.tracks.split(",") if t.strip()]
                except ValueError:
                    pass
            
            # Remove redundant OCR from objects section in description
            desc_parts = frame_row.description.split(" | ")
            if len(desc_parts) >= 2:
                obj_part = desc_parts[1]
                if ", with detected text:" in obj_part:
                    obj_part = obj_part.split(", with detected text:")[0]
                desc_parts[1] = obj_part
            cleaned_db_desc = " | ".join(desc_parts)

            enriched_desc = cleaned_db_desc
            active_names = []
            for t in frame_track_ids:
                active_track_ids.add(t)
                for row in rt_events:
                    if row.get("track_id") == str(t) and row.get("name") and row.get("name").lower() != "unknown":
                        active_names.append(f"{row.get('name')} (Track {t})")
                        break
            
            if active_names:
                enriched_desc = f"{cleaned_db_desc} [Real-time Identity: {', '.join(active_names)}]"

            # Generate proxy clip URL through FastAPI (avoids MinIO CORS issues)
            clip_object_name = f"extracted_clips/{video_id}/clip_frame_{frame_row.frame_number}_{frame_row.timestamp_offset:.2f}s.webm"
            clip_url = f"/api/search/clip/{video_id}/{frame_row.frame_number}?timestamp={frame_row.timestamp_offset:.2f}"
            # Check if clip already exists in MinIO; if not, it will be generated shortly by Celery
            try:
                self.minio_client.stat_object("extracted-search-clips", clip_object_name)
            except Exception:
                # Clip doesn't exist yet — the Celery task will generate it
                pass

            results.append({
                "frame_id": frame_row.frame_number,
                "timestamp": round(frame_row.timestamp_offset, 2),
                "similarity": sim,
                "description": enriched_desc,
                "clip_url": clip_url,
                "track_ids": frame_track_ids
            })
            raw_descriptions_map[frame_row.frame_number] = frame_row.description.split(" | ")[0]

        # Temporal deduplication: suppress matches close in time to a higher-similarity match (3.0s window)
        deduped_results = []
        sorted_results = sorted(results, key=lambda x: x["similarity"], reverse=True)
        for r in sorted_results:
            is_redundant = False
            for k in deduped_results:
                if abs(r["timestamp"] - k["timestamp"]) < 3.0:
                    is_redundant = True
                    break
            if not is_redundant:
                deduped_results.append(r)
                
        results = sorted(deduped_results, key=lambda x: x["timestamp"])

        # Re-build descriptions list from the deduplicated results
        descriptions = [raw_descriptions_map[r["frame_id"]] for r in results]

        # Short-circuit if no frames met the similarity threshold
        if not results:
            return {
                "query": query,
                "total_results": 0,
                "results": [],
                "reid_tracks": {},
                "llm_answer": "No matching events or objects found in this video."
            }

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
                if len(apps) > 8:
                    timestamps_str = ", ".join([f"{a['timestamp']}s" for a in apps[:8]]) + f"... and {len(apps) - 8} other times."
                else:
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
                # Run synchronous LLM inference in a separate thread so Uvicorn doesn't freeze
                llm_answer = await asyncio.to_thread(llm.answer, query, combined_descriptions)
                
                # If LLM reasoner determines no matching events, filter out the results
                if llm_answer == "No matching events or objects found in this video.":
                    results = []
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
