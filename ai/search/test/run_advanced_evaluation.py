#!/usr/bin/env python3
"""
Rawi-Vision Advanced Retrieval Accuracy Evaluation Suite
--------------------------------------------------------
This utility performs mathematically rigorous evaluation of the semantic RAG search
retrieval by computing Precision@K, Recall@K, and F1-Scores against established
ground-truth frames. It also outputs an Accuracy Performance graph.
"""

import time
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Resolve import paths to peer core/ directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.online_search import VideoSearchService

# Ground Truth Definition for Shoplifting (Store) Dataset (total 21 indexed frames)
# Maps query terms to relevant frame IDs
STORE_GROUND_TRUTH = {
    "person": {16, 96, 112, 192, 352, 448, 560, 576, 608, 624},
    "backpack": {192, 352, 448},
    "caution": {16, 96, 112},
    "blue": {16, 112, 192, 448, 560}
}

# Ground Truth Definition for Bear Dataset (total 37 indexed frames)
BEAR_GROUND_TRUTH = {
    "bear": set(range(10, 370, 10)), # Bear is present throughout
    "splashing": {280, 290, 300, 310, 320, 330},
    "swimming": {40, 50, 60, 70, 80, 100, 110}
}

def evaluate_accuracy(artifact_dir: str):
    print("=" * 80)
    print("  RAWI-VISION RIGOROUS ACCURACY EVALUATOR")
    print("=" * 80)
    
    db_path = "video.db"
    faiss_path = "video.faiss"
    map_path = "video.json"
    
    bear_db_path = "online_eval/online_video.db"
    bear_faiss_path = "online_eval/online_video.faiss"
    bear_map_path = "online_eval/online_video.json"
    
    # Initialize Search Services
    service_main = None
    if Path(faiss_path).exists():
        service_main = VideoSearchService(db_path=db_path, faiss_path=faiss_path, map_path=map_path, use_llm=False)
        print("[SUCCESS] Loaded local store database index.")
        
    service_bear = None
    if Path(bear_faiss_path).exists():
        service_bear = VideoSearchService(db_path=bear_db_path, faiss_path=bear_faiss_path, map_path=bear_map_path, use_llm=False)
        print("[SUCCESS] Loaded online bear database index.")
        
    if not service_main and not service_bear:
        print("[ERROR] No indexed databases found for evaluation.")
        sys.exit(1)
        
    accuracy_results = []
    
    # 1. Evaluate Local Store Index
    if service_main:
        print("\nEvaluating Store Dataset Accuracy...")
        for query_term, ground_truth in STORE_GROUND_TRUTH.items():
            res = service_main.search(query=query_term, top_k=5, use_llm=False, extract_clips=False)
            results = res.get("results", [])
            retrieved_ids = [r["frame_id"] for r in results]
            
            # Compute Precision@K (K=1, 3, 5)
            p_1 = len(set(retrieved_ids[:1]) & ground_truth) / 1.0
            p_3 = len(set(retrieved_ids[:3]) & ground_truth) / 3.0
            p_5 = len(set(retrieved_ids[:5]) & ground_truth) / 5.0
            
            # Compute Recall@5
            r_5 = len(set(retrieved_ids[:5]) & ground_truth) / len(ground_truth) if ground_truth else 0.0
            
            # Compute F1-Score@5
            f1_5 = 2 * (p_5 * r_5) / (p_5 + r_5) if (p_5 + r_5) > 0 else 0.0
            
            print(f"- Query: '{query_term}' | P@1: {p_1:.2f} | P@3: {p_3:.2f} | P@5: {p_5:.2f} | R@5: {r_5:.2f} | F1: {f1_5:.2f}")
            accuracy_results.append({
                "query": query_term,
                "dataset": "Store (Local)",
                "p_1": p_1 * 100,
                "p_3": p_3 * 100,
                "p_5": p_5 * 100,
                "r_5": r_5 * 100,
                "f1_5": f1_5 * 100
            })
            
    # 2. Evaluate Online Bear Index
    if service_bear:
        print("\nEvaluating Bear Dataset Accuracy...")
        for query_term, ground_truth in BEAR_GROUND_TRUTH.items():
            res = service_bear.search(query=query_term, top_k=5, use_llm=False, extract_clips=False)
            results = res.get("results", [])
            retrieved_ids = [r["frame_id"] for r in results]
            
            # Compute Precision@K (K=1, 3, 5)
            p_1 = len(set(retrieved_ids[:1]) & ground_truth) / 1.0
            p_3 = len(set(retrieved_ids[:3]) & ground_truth) / 3.0
            p_5 = len(set(retrieved_ids[:5]) & ground_truth) / 5.0
            
            # Compute Recall@5
            r_5 = len(set(retrieved_ids[:5]) & ground_truth) / len(ground_truth) if ground_truth else 0.0
            
            # Compute F1-Score@5
            f1_5 = 2 * (p_5 * r_5) / (p_5 + r_5) if (p_5 + r_5) > 0 else 0.0
            
            print(f"- Query: '{query_term}' | P@1: {p_1:.2f} | P@3: {p_3:.2f} | P@5: {p_5:.2f} | R@5: {r_5:.2f} | F1: {f1_5:.2f}")
            accuracy_results.append({
                "query": query_term,
                "dataset": "Bear (Online)",
                "p_1": p_1 * 100,
                "p_3": p_3 * 100,
                "p_5": p_5 * 100,
                "r_5": r_5 * 100,
                "f1_5": f1_5 * 100
            })

    # Render Graph 3: Advanced Accuracy Performance Breakdown
    print("\n[INFO] Rendering accuracy breakdown graph...")
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
    plt.title('Rawi-Vision Retrieval Accuracy Quality Metrics (Precision/Recall/F1)', fontsize=14, fontweight='bold', pad=15)
    plt.xticks(x, queries, rotation=15, ha='right', fontsize=10, fontweight='bold')
    plt.ylim(0, 110)
    plt.legend(loc='lower left', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
    
    # Put percentages on top of F1-Score bars
    for rect in rects3:
        height = rect.get_height()
        plt.annotate(f'{height:.1f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight='bold', color='#4c1d95')
                    
    plt.tight_layout()
    os.makedirs(artifact_dir, exist_ok=True)
    accuracy_graph_path = os.path.join(artifact_dir, "accuracy_metrics.png")
    plt.savefig(accuracy_graph_path, dpi=300)
    plt.close()
    
    print(f"[SUCCESS] Saved advanced accuracy graph to: {accuracy_graph_path}")
    print("=" * 80)
    print("  ADVANCED RETRIEVAL EVALUATION COMPLETED!")
    print("=" * 80)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, help="Directory to save generated accuracy graphs")
    args = parser.parse_args()
    evaluate_accuracy(args.artifact_dir)
