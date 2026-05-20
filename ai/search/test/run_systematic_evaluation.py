#!/usr/bin/env python3
"""
Rawi-Vision Systematic Evaluation & Benchmarking Suite
------------------------------------------------------
This script performs a rigorous mathematical and structural evaluation of the
Rawi-Vision 1152-dimensional multi-channel semantic RAG vector space.

Evaluations Performed:
1. Retrieval Quality Sweep (Precision@1, Precision@3, Precision@5, Recall@5, F1-Score@5, MAP)
2. Vector Space Baseline Comparison (1152-dim Multi-Channel vs. 384-dim Single-Channel VLM Text)
3. Signal-to-Noise Ratio (SNR) Match Contrast Ratio
4. Chart Generation (accuracy_metrics.png, vector_space_comparison.png, retrieval_snr_contrast.png)
"""

import os
import sys
import time
import json
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Resolve import paths to peer core/ directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.online_search import VideoSearchService, QueryEncoder, FAISSIdx
import faiss
import torch
from sentence_transformers import SentenceTransformer

# Ground Truth Definition for Shoplifting (Store) Dataset (total 21 indexed frames)
STORE_GROUND_TRUTH = {
    "person": {16, 96, 112, 192, 352, 448, 560, 576, 608, 624},
    "backpack": {192, 352, 448},
    "caution": {16, 96, 112},
    "blue": {16, 112, 192, 448, 560}
}

# Ground Truth Definition for Bear Dataset (total 37 indexed frames)
BEAR_GROUND_TRUTH = {
    "bear": set(range(10, 370, 10)),
    "splashing": {280, 290, 300, 310, 320, 330},
    "swimming": {40, 50, 60, 70, 80, 100, 110}
}

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

class BaselineSingleChannelSearcher:
    """
    Simulates a standard single-channel 384-dimensional text search baseline
    by generating embeddings for just the visual caption and matching via FAISS.
    """
    def __init__(self, db_path: str, map_path: str):
        self.db_path = db_path
        self.map_path = map_path
        
        # Load mappings
        with open(map_path) as f:
            self.frame_map = {int(k): v for k, v in json.load(f).items()}
            
        self.emb_model = SentenceTransformer(EMBEDDING_MODEL, device=DEVICE)
        self.index = faiss.IndexFlatIP(384)
        self.frame_ids = []
        
        # Fetch VLM captions from database and generate 384-dim embeddings
        self._build_baseline_index()

    def _build_baseline_index(self):
        print(f"[BASELINE] Generating 384-dim baseline index from {self.db_path}...")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Get frame descriptions sorted by mapped order
            sorted_map_keys = sorted(self.frame_map.keys())
            embeddings = []
            
            for key in sorted_map_keys:
                fid = self.frame_map[key]
                row = cursor.execute("SELECT description FROM frames WHERE frame_id=?", (fid,)).fetchone()
                if row:
                    full_desc = row[0]
                    # The VLM visual description is before the first pipe "|"
                    vlm_caption = full_desc.split("|")[0].strip()
                    self.frame_ids.append(fid)
                    
                    # Generate 384-dim embedding
                    emb = self.emb_model.encode(vlm_caption, convert_to_numpy=True)
                    # Normalize for inner product (cosine similarity)
                    norm = np.linalg.norm(emb) + 1e-8
                    embeddings.append(emb / norm)
            
            if embeddings:
                embeddings_np = np.vstack(embeddings).astype(np.float32)
                self.index.add(embeddings_np)
                print(f"[BASELINE] Loaded {len(self.frame_ids)} frames into baseline FAISS index.")

    def search(self, query: str, top_k: int = 5) -> list:
        # Encode standard query in 384-dim
        q_emb = self.emb_model.encode(query, convert_to_numpy=True)
        norm = np.linalg.norm(q_emb) + 1e-8
        q_emb = (q_emb / norm).astype(np.float32).reshape(1, -1)
        
        distances, indices = self.index.search(q_emb, min(top_k, len(self.frame_ids)))
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:
                continue
            fid = self.frame_ids[int(idx)]
            sim = float(dist) * 100
            results.append({"frame_id": fid, "similarity": sim})
        return results

def compute_metrics(retrieved_ids, ground_truth):
    if not ground_truth:
        return 0, 0, 0, 0, 0, 0
    
    # Compute Precision@K (K=1, 3, 5)
    p_1 = len(set(retrieved_ids[:1]) & ground_truth) / 1.0
    p_3 = len(set(retrieved_ids[:3]) & ground_truth) / 3.0
    p_5 = len(set(retrieved_ids[:5]) & ground_truth) / 5.0
    
    # Compute Recall@5
    r_5 = len(set(retrieved_ids[:5]) & ground_truth) / len(ground_truth)
    
    # Compute F1-Score@5
    f1_5 = 2 * (p_5 * r_5) / (p_5 + r_5) if (p_5 + r_5) > 0 else 0.0
    
    # Compute Average Precision (AP) for MAP calculation
    ap_sum = 0.0
    hits = 0
    for idx, fid in enumerate(retrieved_ids):
        if fid in ground_truth:
            hits += 1
            ap_sum += hits / (idx + 1)
    ap = ap_sum / min(len(ground_truth), len(retrieved_ids)) if len(ground_truth) > 0 and len(retrieved_ids) > 0 else 0.0
    
    return p_1, p_3, p_5, r_5, f1_5, ap

def run_systematic_benchmark(artifact_dir: str):
    print("=" * 80)
    print("  RAWI-VISION SYSTEMATIC EVALUATION BENCHMARK SUITE")
    print("=" * 80)
    
    # Force offline loading
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    
    db_path = "video.db"
    faiss_path = "video.faiss"
    map_path = "video.json"
    
    bear_db_path = "online_eval/online_video.db"
    bear_faiss_path = "online_eval/online_video.faiss"
    bear_map_path = "online_eval/online_video.json"
    
    # Verify indexes
    service_main = None
    if Path(faiss_path).exists():
        service_main = VideoSearchService(db_path=db_path, faiss_path=faiss_path, map_path=map_path, use_llm=False)
        print("[SUCCESS] Loaded main store database index.")
        
    service_bear = None
    if Path(bear_faiss_path).exists():
        service_bear = VideoSearchService(db_path=bear_db_path, faiss_path=bear_faiss_path, map_path=bear_map_path, use_llm=False)
        print("[SUCCESS] Loaded online bear database index.")
        
    if not service_main and not service_bear:
        print("[ERROR] No database indexes found. Please ensure indexes are built.")
        sys.exit(1)
        
    # Initialize baseline searchers
    baseline_main = None
    if service_main:
        baseline_main = BaselineSingleChannelSearcher(db_path, map_path)
        
    baseline_bear = None
    if service_bear:
        baseline_bear = BaselineSingleChannelSearcher(bear_db_path, bear_map_path)
        
    accuracy_results = []
    comparison_results = []
    snr_results = []
    
    # 1. Benchmark Shoplifting Store Dataset
    if service_main and baseline_main:
        print("\n[INFO] Evaluating Store (Local) Dataset...")
        for query_term, ground_truth in STORE_GROUND_TRUTH.items():
            # A. Default Multi-Channel Search (1152-dim)
            res_multi = service_main.search(query=query_term, top_k=5, use_llm=False, extract_clips=False)
            multi_results = res_multi.get("results", [])
            multi_ids = [r["frame_id"] for r in multi_results]
            
            # Compute Multi-Channel Metrics
            mp1, mp3, mp5, mr5, mf1, map_score = compute_metrics(multi_ids, ground_truth)
            
            # B. Baseline Single-Channel Search (384-dim)
            baseline_results = baseline_main.search(query=query_term, top_k=5)
            baseline_ids = [r["frame_id"] for r in baseline_results]
            
            # Compute Baseline Metrics
            bp1, bp3, bp5, br5, bf1, bap_score = compute_metrics(baseline_ids, ground_truth)
            
            # C. Compute SNR Contrast
            # Fetch all frame IDs and compute similarities
            all_frames = service_main.db.get_all()
            q_emb = service_main.encoder.encode(query_term)
            
            similarities_multi = []
            similarities_base = []
            
            # Helper to calculate cosine similarities manually for all frames
            for frame in all_frames:
                # Get the multi-channel vector
                # Let's search FAISS directly for this frame
                pass
            
            # We can use the FAISS search distance scores for matches vs others
            # Let's search with a large top_k to get all database frame scores
            res_all_multi = service_main.faiss.search(q_emb, len(all_frames))
            multi_scores = {fid: score for fid, score in res_all_multi}
            
            # For baseline, query the baseline FAISS index for all frames
            q_emb_base = baseline_main.emb_model.encode(query_term, convert_to_numpy=True)
            norm = np.linalg.norm(q_emb_base) + 1e-8
            q_emb_base = (q_emb_base / norm).astype(np.float32).reshape(1, -1)
            dist_base, ind_base = baseline_main.index.search(q_emb_base, len(all_frames))
            
            base_scores = {}
            for idx, d in zip(ind_base[0], dist_base[0]):
                if idx != -1:
                    fid = baseline_main.frame_ids[int(idx)]
                    base_scores[fid] = float(d) * 100
            
            # Calculate SNR ratios
            multi_best = max(multi_scores.values()) if multi_scores else 0.0
            non_match_multi = [score for fid, score in multi_scores.items() if fid not in ground_truth]
            multi_avg_non = np.mean(non_match_multi) if non_match_multi else 1.0
            snr_multi = multi_best / (multi_avg_non + 1e-8)
            
            base_best = max(base_scores.values()) if base_scores else 0.0
            non_match_base = [score for fid, score in base_scores.items() if fid not in ground_truth]
            base_avg_non = np.mean(non_match_base) if non_match_base else 1.0
            snr_base = base_best / (base_avg_non + 1e-8)
            
            print(f"- Query: '{query_term}' | Multi-Channel F1: {mf1:.2f} | Baseline F1: {bf1:.2f} | Multi SNR: {snr_multi:.2f}x | Baseline SNR: {snr_base:.2f}x")
            
            accuracy_results.append({
                "query": query_term,
                "dataset": "Store (Local)",
                "p_1": mp1 * 100,
                "p_3": mp3 * 100,
                "p_5": mp5 * 100,
                "r_5": mr5 * 100,
                "f1_5": mf1 * 100,
                "map": map_score * 100
            })
            
            comparison_results.append({
                "query": query_term,
                "dataset": "Store",
                "multi_f1": mf1 * 100,
                "base_f1": bf1 * 100,
                "multi_p5": mp5 * 100,
                "base_p5": bp5 * 100
            })
            
            snr_results.append({
                "query": query_term,
                "dataset": "Store",
                "multi_snr": snr_multi,
                "base_snr": snr_base
            })
            
    # 2. Benchmark Bear Dataset
    if service_bear and baseline_bear:
        print("\n[INFO] Evaluating Bear (Online) Dataset...")
        for query_term, ground_truth in BEAR_GROUND_TRUTH.items():
            # A. Default Multi-Channel Search (1152-dim)
            res_multi = service_bear.search(query=query_term, top_k=5, use_llm=False, extract_clips=False)
            multi_results = res_multi.get("results", [])
            multi_ids = [r["frame_id"] for r in multi_results]
            
            # Compute Multi-Channel Metrics
            mp1, mp3, mp5, mr5, mf1, map_score = compute_metrics(multi_ids, ground_truth)
            
            # B. Baseline Single-Channel Search (384-dim)
            baseline_results = baseline_bear.search(query=query_term, top_k=5)
            baseline_ids = [r["frame_id"] for r in baseline_results]
            
            # Compute Baseline Metrics
            bp1, bp3, bp5, br5, bf1, bap_score = compute_metrics(baseline_ids, ground_truth)
            
            # C. Compute SNR Contrast
            all_frames = service_bear.db.get_all()
            q_emb = service_bear.encoder.encode(query_term)
            
            res_all_multi = service_bear.faiss.search(q_emb, len(all_frames))
            multi_scores = {fid: score for fid, score in res_all_multi}
            
            q_emb_base = baseline_bear.emb_model.encode(query_term, convert_to_numpy=True)
            norm = np.linalg.norm(q_emb_base) + 1e-8
            q_emb_base = (q_emb_base / norm).astype(np.float32).reshape(1, -1)
            dist_base, ind_base = baseline_bear.index.search(q_emb_base, len(all_frames))
            
            base_scores = {}
            for idx, d in zip(ind_base[0], dist_base[0]):
                if idx != -1:
                    fid = baseline_bear.frame_ids[int(idx)]
                    base_scores[fid] = float(d) * 100
                    
            multi_best = max(multi_scores.values()) if multi_scores else 0.0
            non_match_multi = [score for fid, score in multi_scores.items() if fid not in ground_truth]
            multi_avg_non = np.mean(non_match_multi) if non_match_multi else 1.0
            snr_multi = multi_best / (multi_avg_non + 1e-8)
            
            base_best = max(base_scores.values()) if base_scores else 0.0
            non_match_base = [score for fid, score in base_scores.items() if fid not in ground_truth]
            base_avg_non = np.mean(non_match_base) if non_match_base else 1.0
            snr_base = base_best / (base_avg_non + 1e-8)
            
            print(f"- Query: '{query_term}' | Multi-Channel F1: {mf1:.2f} | Baseline F1: {bf1:.2f} | Multi SNR: {snr_multi:.2f}x | Baseline SNR: {snr_base:.2f}x")
            
            accuracy_results.append({
                "query": query_term,
                "dataset": "Bear (Online)",
                "p_1": mp1 * 100,
                "p_3": mp3 * 100,
                "p_5": mp5 * 100,
                "r_5": mr5 * 100,
                "f1_5": mf1 * 100,
                "map": map_score * 100
            })
            
            comparison_results.append({
                "query": query_term,
                "dataset": "Bear",
                "multi_f1": mf1 * 100,
                "base_f1": bf1 * 100,
                "multi_p5": mp5 * 100,
                "base_p5": bp5 * 100
            })
            
            snr_results.append({
                "query": query_term,
                "dataset": "Bear",
                "multi_snr": snr_multi,
                "base_snr": snr_base
            })
            
    # Ensure artifact directory exists
    os.makedirs(artifact_dir, exist_ok=True)
    
    # ------------------------------------------------------------------
    # GRAPH 1: Retrieval Accuracy Quality Metrics (accuracy_metrics.png)
    # ------------------------------------------------------------------
    print("\n[INFO] Rendering accuracy_metrics.png...")
    plt.figure(figsize=(10, 6))
    
    queries = [f"{d['query']} ({d['dataset'].split()[0]})" for d in accuracy_results]
    p5_scores = [d["p_5"] for d in accuracy_results]
    r5_scores = [d["r_5"] for d in accuracy_results]
    f1_scores = [d["f1_5"] for d in accuracy_results]
    
    x = np.arange(len(queries))
    width = 0.25
    
    rects1 = plt.bar(x - width, p5_scores, width, label='Precision @ 5', color='#0284c7', edgecolor='#0369a1')
    rects2 = plt.bar(x, r5_scores, width, label='Recall @ 5', color='#22c55e', edgecolor='#16a34a', alpha=0.8)
    rects3 = plt.bar(x + width, f1_scores, width, label='F1-Score @ 5', color='#8b5cf6', edgecolor='#6d28d9', alpha=0.8)
    
    plt.ylabel('Percentage Score (%)', fontsize=12, fontweight='bold', labelpad=10)
    plt.title('Rawi-Vision Retrieval Accuracy Quality Metrics', fontsize=14, fontweight='bold', pad=15)
    plt.xticks(x, queries, rotation=15, ha='right', fontsize=10, fontweight='bold')
    plt.ylim(0, 115)
    plt.legend(loc='upper left', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
    
    for rect in rects3:
        height = rect.get_height()
        plt.annotate(f'{height:.1f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight='bold', color='#4c1d95')
                    
    plt.tight_layout()
    plt.savefig(os.path.join(artifact_dir, "accuracy_metrics.png"), dpi=300)
    plt.close()
    
    # ------------------------------------------------------------------
    # GRAPH 2: Vector Space Baseline Comparison (vector_space_comparison.png)
    # ------------------------------------------------------------------
    print("[INFO] Rendering vector_space_comparison.png...")
    plt.figure(figsize=(10, 6))
    
    queries_comp = [f"{d['query']} ({d['dataset']})" for d in comparison_results]
    multi_f1s = [d["multi_f1"] for d in comparison_results]
    base_f1s = [d["base_f1"] for d in comparison_results]
    
    x = np.arange(len(queries_comp))
    width = 0.35
    
    rects1 = plt.bar(x - width/2, multi_f1s, width, label='Multi-Channel Vector (1152-dim)', color='#3b82f6', edgecolor='#1d4ed8')
    rects2 = plt.bar(x + width/2, base_f1s, width, label='Single-Channel Text (384-dim)', color='#94a3b8', edgecolor='#475569')
    
    plt.ylabel('F1-Score @ 5 (%)', fontsize=12, fontweight='bold', labelpad=10)
    plt.title('Vector Space Design: Multi-Channel vs. Single-Channel Baseline', fontsize=14, fontweight='bold', pad=15)
    plt.xticks(x, queries_comp, rotation=15, ha='right', fontsize=10, fontweight='bold')
    plt.ylim(0, 115)
    plt.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
    
    # Add values on top of bars
    for rect in rects1:
        height = rect.get_height()
        plt.annotate(f'{height:.0f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight='bold', color='#1e3a8a')
    for rect in rects2:
        height = rect.get_height()
        plt.annotate(f'{height:.0f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight='bold', color='#334155')
                    
    plt.tight_layout()
    plt.savefig(os.path.join(artifact_dir, "vector_space_comparison.png"), dpi=300)
    plt.close()
    
    # ------------------------------------------------------------------
    # GRAPH 3: Signal-to-Noise Ratio Matching Contrast (retrieval_snr_contrast.png)
    # ------------------------------------------------------------------
    print("[INFO] Rendering retrieval_snr_contrast.png...")
    plt.figure(figsize=(10, 6))
    
    queries_snr = [f"{d['query']} ({d['dataset']})" for d in snr_results]
    multi_snrs = [d["multi_snr"] for d in snr_results]
    base_snrs = [d["base_snr"] for d in snr_results]
    
    x = np.arange(len(queries_snr))
    width = 0.35
    
    rects1 = plt.bar(x - width/2, multi_snrs, width, label='Multi-Channel (High Contrast)', color='#10b981', edgecolor='#047857')
    rects2 = plt.bar(x + width/2, base_snrs, width, label='Single-Channel (Low Contrast)', color='#f59e0b', edgecolor='#b45309')
    
    plt.ylabel('SNR Contrast Ratio (Match vs Background)', fontsize=12, fontweight='bold', labelpad=10)
    plt.title('Retrieval Contrast Ratio: Multi-Channel vs. Single-Channel Space', fontsize=14, fontweight='bold', pad=15)
    plt.xticks(x, queries_snr, rotation=15, ha='right', fontsize=10, fontweight='bold')
    plt.ylim(0, max(max(multi_snrs), max(base_snrs)) * 1.2)
    plt.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
    
    # Draw contrast safety bounds line
    plt.axhline(y=2.0, color='#ef4444', linestyle=':', label='Target SNR Safety Bound (2.0x)')
    plt.legend(loc='upper right')
    
    for rect in rects1:
        height = rect.get_height()
        plt.annotate(f'{height:.2f}x',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight='bold', color='#064e3b')
    for rect in rects2:
        height = rect.get_height()
        plt.annotate(f'{height:.2f}x',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight='bold', color='#78350f')
                    
    plt.tight_layout()
    plt.savefig(os.path.join(artifact_dir, "retrieval_snr_contrast.png"), dpi=300)
    plt.close()
    
    print("\n" + "=" * 80)
    print("  SYSTEMATIC EVALUATION COMPLETED & ALL PROOF GRAPHS SAVED!")
    print("=" * 80)
    print(f"Generated assets saved to: {os.path.abspath(artifact_dir)}")
    print("=" * 80)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", default="docs/", help="Directory to save generated accuracy and comparison graphs")
    args = parser.parse_args()
    run_systematic_benchmark(args.artifact_dir)
