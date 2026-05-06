#!/usr/bin/env python3

import json
import sqlite3
import argparse
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
        messages = [
            {"role": "system", "content": "You are an assistant that answers questions based on video frame descriptions. Use only the provided descriptions. Keep answers concise."},
            {"role": "user", "content": f"Context (frame descriptions):\n{context_str}\n\nQuestion: {query}"}
        ]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,          # deterministic
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
                 map_path="video.json", use_llm=False, llm_model_name=None):
        self.db = VideoDB(db_path)
        self.faiss = FAISSIdx(faiss_path, map_path)
        self.encoder = QueryEncoder()

        self.llm = None
        if use_llm:
            try:
                model = llm_model_name or "HuggingFaceTB/SmolLM2-1.7B-Instruct"
                self.llm = LLMReasoner(model_name=model)
            except Exception as e:
                print(f"[WARN] Failed to load LLM: {e}")

    def search(self, query: str, top_k: int = 10, use_llm: bool = True) -> dict:
        query_emb = self.encoder.encode(query)
        matches = self.faiss.search(query_emb, top_k)

        results = []
        descriptions = []
        for fid, sim in matches:
            frame = self.db.get(fid)
            if frame:
                results.append(SearchResult(frame.frame_id, frame.timestamp,
                                            frame.description, sim))
                descriptions.append(frame.description)

        llm_answer = None
        if use_llm and self.llm and descriptions:
            try:
                llm_answer = self.llm.answer(query, descriptions)
            except Exception as e:
                print(f"[WARN] LLM failed: {e}")
                llm_answer = "LLM reasoning unavailable."

        return {
            "query": query,
            "total_results": len(results),
            "results": [asdict(r) for r in results],
            "llm_answer": llm_answer,
            "note": "Similarity scores are percentages (0-100). Scores above 20% indicate potential matches."
        }

# ----------------------------------------------------------------------
# FastAPI server (optional)
# ----------------------------------------------------------------------

def start_server(service: VideoSearchService, host="0.0.0.0", port=8000):
    from fastapi import FastAPI
    from pydantic import BaseModel
    import uvicorn

    app = FastAPI(title="Video Search API")

    class SearchQuery(BaseModel):
        query: str
        top_k: int = 10
        use_llm: bool = True

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/search")
    def search_endpoint(req: SearchQuery):
        result = service.search(req.query, req.top_k, req.use_llm)
        return result

    print(f"Starting API on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Online video search (CLI or API)")
    parser.add_argument("command", nargs="?", choices=["search", "serve"], default="search",
                        help="Run a single search or start the API server")
    parser.add_argument("query", nargs="?", help="Text query (for 'search' command)")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM reasoning (SmolLM2)")
    parser.add_argument("--llm-model", type=str, default=None,
                        help="LLM model name (default HuggingFaceTB/SmolLM2-1.7B-Instruct)")
    parser.add_argument("--db", default="video.db")
    parser.add_argument("--faiss", default="video.faiss")
    parser.add_argument("--map", default="video.json")
    parser.add_argument("--output", help="Save JSON output to file")
    parser.add_argument("--host", default="0.0.0.0", help="API server host")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    args = parser.parse_args()

    service = VideoSearchService(db_path=args.db, faiss_path=args.faiss,
                                 map_path=args.map, use_llm=args.use_llm,
                                 llm_model_name=args.llm_model)

    if args.command == "serve":
        start_server(service, args.host, args.port)
    else:
        if not args.query:
            print("Error: query required for 'search' command")
            return
        result = service.search(args.query, args.top_k, args.use_llm)
        print(json.dumps(result, indent=2))
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

if __name__ == "__main__":
    main()