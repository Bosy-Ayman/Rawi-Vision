import os
import csv
import json
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import re

from minio import Minio
from sqlalchemy import desc, text
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from search.models.search import IndexedVideo, VideoFrame

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
COMBINED_DIM = EMBEDDING_DIM * 3

STOPWORDS = {
    'a', 'an', 'the', 'in', 'on', 'at', 'by', 'with', 'for', 'of', 'and', 'or', 'is', 'are', 'was', 'were', 
    'be', 'been', 'being', 'to', 'from', 'he', 'she', 'it', 'they', 'them', 'his', 'her', 'their', 'him', 
    'who', 'whom', 'what', 'which', 'whose', 'this', 'that', 'these', 'those', 'i', 'you', 'we', 'us'
}

def extract_query_keywords(query: str) -> set:
    """Extract content words (non-stopwords) from query"""
    words = set(re.findall(r'[a-zA-Z0-9]+', query.lower()))
    return {w for w in words if w not in STOPWORDS and len(w) > 1}

def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

# ----------------------------------------------------------------------
# Query Encoder (Matches offline frame indexing dimension of 1152)
# ----------------------------------------------------------------------

class SafeStreamWrapper:
    def __init__(self, original_stream):
        self._original_stream = original_stream

    def write(self, s):
        try:
            if self._original_stream is not None:
                return self._original_stream.write(s)
        except Exception:
            pass
        return 0

    def flush(self):
        try:
            if self._original_stream is not None:
                return self._original_stream.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._original_stream, name)

def patch_streams():
    import sys
    # Limit PyTorch internal threads to prevent high CPU container kills
    try:
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
    except Exception:
        pass

    if sys.stdout is not None and not isinstance(sys.stdout, SafeStreamWrapper):
        sys.stdout = SafeStreamWrapper(sys.stdout)
    if sys.stderr is not None and not isinstance(sys.stderr, SafeStreamWrapper):
        sys.stderr = SafeStreamWrapper(sys.stderr)

class QueryEncoder:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Force tqdm/colorama to initialize and wrap standard streams first
        try:
            import tqdm
        except Exception:
            pass
        try:
            import colorama
            colorama.init()
        except Exception:
            pass
        # Patch the colorama-wrapped standard streams
        patch_streams()

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
        # Force tqdm/colorama to initialize first
        try:
            import tqdm
        except Exception:
            pass
        try:
            import colorama
            colorama.init()
        except Exception:
            pass
        # Patch the wrapped standard streams
        patch_streams()

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
            context_words = {w for w in re.findall(r'[a-zA-Z0-9]+', context_lower) if w not in STOPWORDS}
            
            # Fuzzy match content words against context words
            # If every content word matches at least one word in context_words (exactly, as substring, or with low Levenshtein distance),
            # we consider it a direct word match and bypass the LLM validator.
            has_direct_word_match = True
            for cw in content_words:
                word_matched = False
                for ctx_w in context_words:
                    if cw == ctx_w or (len(cw) >= 3 and len(ctx_w) >= 3 and (cw in ctx_w or ctx_w in cw)):
                        word_matched = True
                        break
                    dist_limit = 2 if len(cw) >= 5 or len(ctx_w) >= 5 else 1
                    if levenshtein_distance(cw, ctx_w) <= dist_limit:
                        word_matched = True
                        break
                if not word_matched:
                    has_direct_word_match = False
                    break

        # If no direct keyword match, run Yes/No validation using LLM
        is_match = True
        if not has_direct_word_match:
            messages_val = [
                {"role": "system", "content": "You are a strict validator. Reply with ONLY 'Yes' or 'No'."},
                {"role": "user", "content": f"Context:\n{fused_visual}\n\nQuestion: Does the Context contain any description, mention, or objects related to '{query}'? Reply with ONLY 'Yes' or 'No'."}
            ]
            prompt_val = self.tokenizer.apply_chat_template(messages_val, tokenize=False, add_generation_prompt=True)
            inputs_val = self.tokenizer(prompt_val, return_tensors="pt", truncation=True, max_length=1024)
            inputs_val = {k: v.to(self.model.device) for k, v in inputs_val.items()}
            with torch.no_grad():
                outputs_val = self.model.generate(
                    **inputs_val,
                    max_new_tokens=10,
                    do_sample=False,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            input_length_val = inputs_val["input_ids"].shape[1]
            val_answer = self.tokenizer.decode(outputs_val[0][input_length_val:], skip_special_tokens=True).strip()
            
            val_clean = val_answer.lower()
            # A match is ONLY valid if the answer explicitly says "yes" and does not say "no"
            if "yes" in val_clean and "no" not in val_clean:
                is_match = True
            else:
                is_match = False
            print(f"[DEBUG LLM Validator] Query: {repr(query)} | Raw Answer: {repr(val_answer)} | val_clean: {repr(val_clean)} | is_match: {is_match}")


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
                        sample = f.read(2048)
                        f.seek(0)
                        
                        has_header = False
                        if sample:
                            first_line = sample.split("\n")[0].lower()
                            if "track_id" in first_line or "name" in first_line or "event" in first_line:
                                has_header = True
                                
                        if has_header:
                            reader = csv.DictReader(f)
                            for row in reader:
                                events.append(row)
                        else:
                            fieldnames = ["timestamp", "event_type", "track_id", "name", "confidence", "metadata"]
                            reader = csv.DictReader(f, fieldnames=fieldnames)
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
        # We increase the limit to 100 to allow candidate filtering/boosting in python
        stmt = (
            select(VideoFrame, (1 - VideoFrame.embedding.cosine_distance(query_vector)).label("similarity"))
            .filter(VideoFrame.video_id == video_id)
            .order_by(desc("similarity"))
            .limit(100)
        )
        
        result = await db.execute(stmt)
        rows = result.all()

        # Fetch all appearances for this video from video_appearances table
        stmt_apps = text("""
            SELECT va.frame_number, va.employee_id, e.first_name, e.last_name
            FROM video_appearances va
            JOIN employees e ON va.employee_id = e.id
            WHERE va.video_id = :video_id
        """)
        result_apps = await db.execute(stmt_apps, {"video_id": str(video_id)})
        apps_rows = result_apps.fetchall()
        
        # Build mapping of frame_number -> list of employee names
        # and frame_number -> set of employee IDs
        frame_to_names = {}
        frame_to_emp_ids = {}
        for frame_num, emp_id, first_name, last_name in apps_rows:
            full_name = f"{first_name} {last_name}".strip()
            
            if frame_num not in frame_to_names:
                frame_to_names[frame_num] = []
            if full_name not in frame_to_names[frame_num]:
                frame_to_names[frame_num].append(full_name)
                
            if frame_num not in frame_to_emp_ids:
                frame_to_emp_ids[frame_num] = set()
            frame_to_emp_ids[frame_num].add(str(emp_id))

        # Query all employees to match query keywords for identity-based filtering
        stmt_emp = text("SELECT id, first_name, last_name FROM employees")
        result_emp = await db.execute(stmt_emp)
        employees = result_emp.fetchall()
        
        # Extract query keywords and clean the full query string
        query_keywords = extract_query_keywords(query)
        q_clean = query.strip().lower()
        
        matched_employee_ids = set()
        for emp_id, first_name, last_name in employees:
            first_name_clean = first_name.strip().lower()
            last_name_clean = last_name.strip().lower()
            emp_name_parts = {first_name_clean, last_name_clean}
            fullname = f"{first_name_clean} {last_name_clean}"
            fullname_no_space = f"{first_name_clean}{last_name_clean}"
            
            matched = False
            # 1. Direct query-level checks
            if q_clean == first_name_clean or q_clean == last_name_clean or q_clean == fullname:
                matched = True
            elif len(q_clean) >= 3 and (q_clean in fullname or fullname in q_clean or q_clean in fullname_no_space):
                matched = True
            else:
                # 2. Keyword-level checks
                for keyword in query_keywords:
                    for part in emp_name_parts:
                        if keyword == part or keyword in part or part in keyword:
                            matched = True
                            break
                        dist_limit = 2 if len(part) >= 5 or len(keyword) >= 5 else 1
                        if levenshtein_distance(keyword, part) <= dist_limit:
                            matched = True
                            break
                    if matched:
                        break
                    
            if matched:
                matched_employee_ids.add(str(emp_id))

        results = []
        raw_descriptions_map = {}  # map frame_number to clean VLM desc
        active_employee_names = set()

        SIM_THRESHOLD = 35.0

        for frame_row, similarity_score in rows:
            # Convert decimal similarity to percentage
            sim = round(float(similarity_score) * 100, 1)
            
            # Skip matches that are below the similarity threshold
            if sim < SIM_THRESHOLD:
                continue
                
            frame_num = frame_row.frame_number
            frame_emp_ids = frame_to_emp_ids.get(frame_num, set())
            
            # Hard filter: If query matched an identity in events, restrict candidates to that identity
            if matched_employee_ids:
                if not (frame_emp_ids & matched_employee_ids):
                    continue
            
            # Remove redundant OCR from objects section in description
            desc_parts = frame_row.description.split(" | ")
            if len(desc_parts) >= 2:
                obj_part = desc_parts[1]
                if ", with detected text:" in obj_part:
                    obj_part = obj_part.split(", with detected text:")[0]
                desc_parts[1] = obj_part
            cleaned_db_desc = " | ".join(desc_parts)

            frame_identities = frame_to_names.get(frame_num, [])
            for name in frame_identities:
                active_employee_names.add(name)
                
            enriched_desc = cleaned_db_desc
            if frame_identities:
                enriched_desc = f"{cleaned_db_desc} [Real-time Identity: {', '.join(frame_identities)}]"

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
                "track_ids": [],
                "identities": frame_identities
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
                
        # Limit to top_k matching candidates
        top_k_results = deduped_results[:top_k]
        results = sorted(top_k_results, key=lambda x: x["timestamp"])

        # Re-build descriptions list from the deduplicated results
        descriptions = [raw_descriptions_map[r["frame_id"]] for r in results]

        # Short-circuit if no frames met the similarity threshold or filter
        if not results:
            return {
                "query": query,
                "total_results": 0,
                "results": [],
                "reid_tracks": {},
                "llm_answer": "No matching events or objects found in this video."
            }

        # Build Re-ID timeline of when each matched employee was seen throughout the video
        reid_tracks = {}
        if active_employee_names:
            # Query all appearances for these employees in this video to trace their timeline
            stmt_all_apps = text("""
                SELECT va.frame_number, va.timestamp_offset, e.first_name, e.last_name
                FROM video_appearances va
                JOIN employees e ON va.employee_id = e.id
                WHERE va.video_id = :video_id
                ORDER BY va.timestamp_offset
            """)
            result_all_apps = await db.execute(stmt_all_apps, {"video_id": str(video_id)})
            all_apps = result_all_apps.fetchall()
            
            for name in active_employee_names:
                appearances = []
                for frame_num, ts_offset, first_name, last_name in all_apps:
                    full_name = f"{first_name} {last_name}".strip()
                    if full_name == name:
                        appearances.append({
                            "frame_id": frame_num,
                            "timestamp": round(ts_offset, 2)
                        })
                if appearances:
                    reid_tracks[name] = appearances

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
                llm_lower = llm_answer.lower() if llm_answer else ""
                negative_phrases = [
                    "no matching events", 
                    "no matching objects", 
                    "no information", 
                    "not found in this video",
                    "not found in the",
                    "not mentioned in the", 
                    "does not contain", 
                    "does not mention",
                    "no events or objects found"
                ]
                if llm_answer == "No matching events or objects found in this video." or any(phrase in llm_lower for phrase in negative_phrases):
                    results = []
                    llm_answer = "No matching events or objects found in this video."
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
