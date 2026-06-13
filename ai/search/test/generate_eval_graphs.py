#!/usr/bin/env python3
"""
Rawi-Vision Pipeline Graph Generation & Benchmarking Utility
-----------------------------------------------------------
This script queries both default and online indexed video databases,
measures retrieval latencies and similarity score distributions,
and generates premium visual proof graphs saved directly to the brain artifacts directory.
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

def generate_graphs(artifact_dir: str):
    print("=" * 80)
    print("  RAWI-VISION GRAPH PROOFS GENERATOR")
    print("=" * 80)
    
    # 1. Resolve Indexed Databases
    db_path = "video.db"
    faiss_path = "video.faiss"
    map_path = "video.json"
    
    bear_db_path = "online_eval/online_video.db"
    bear_faiss_path = "online_eval/online_video.faiss"
    bear_map_path = "online_eval/online_video.json"
    
    # Setup queries for main video (convenience store)
    convenience_queries = [
        {"query": "person in blue shirt", "category": "Visual Attributes"},
        {"query": "backpack", "category": "Objects"},
        {"query": "caution signage", "category": "OCR Text Detection"},
        {"query": "Abdelrahman", "category": "Re-ID Name Fusion"},
        {"query": "empty aisle", "category": "Zero-Result Fallback"}
    ]
    
    # Setup queries for online video (bear river)
    bear_queries = [
        {"query": "bear in splashing water", "category": "Visual Attributes"},
        {"query": "animal catching fish", "category": "Objects"},
        {"query": "fast flowing river", "category": "OCR/Layout Description"},
        {"query": "swimming", "category": "Action/Motion Profile"},
        {"query": "motorcycle or car", "category": "Zero-Result Fallback"}
    ]
    
    # Initialize services
    print("[INFO] Initializing search services...")
    service_main = None
    if Path(faiss_path).exists():
        service_main = VideoSearchService(db_path=db_path, faiss_path=faiss_path, map_path=map_path, use_llm=False)
        print("[SUCCESS] Loaded main store database index.")
    
    service_bear = None
    if Path(bear_faiss_path).exists():
        service_bear = VideoSearchService(db_path=bear_db_path, faiss_path=bear_faiss_path, map_path=bear_map_path, use_llm=False)
        print("[SUCCESS] Loaded online bear database index.")
        
    if not service_main and not service_bear:
        print("[ERROR] No indexed databases found. Please run offline_index.py or evaluate_online_video.py first.")
        sys.exit(1)
        
    # Execute benchmarks
    benchmark_data = []
    
    # Benchmarking Main Video
    if service_main:
        print("\nBenchmarking Main Video (Shoplifting)...")
        for cq in convenience_queries:
            q = cq["query"]
            # Warmup
            _ = service_main.search(query=q, top_k=5, use_llm=False, extract_clips=False)
            
            latencies = []
            similarities = []
            for _ in range(5): # average over 5 iterations for precision
                t0 = time.time()
                res = service_main.search(query=q, top_k=3, use_llm=False, extract_clips=False)
                latencies.append((time.time() - t0) * 1000)
            
            results = res.get("results", [])
            for r in results:
                similarities.append(r["similarity"])
            
            avg_lat = np.mean(latencies)
            max_sim = similarities[0] if similarities else 0.0
            
            print(f"- Query: '{q}' | Latency: {avg_lat:.2f}ms | Top Match Similarity: {max_sim:.1f}%")
            benchmark_data.append({
                "query": q,
                "dataset": "Store (Local)",
                "category": cq["category"],
                "latency": avg_lat,
                "top_similarity": max_sim,
                "all_similarities": similarities
            })
            
    # Benchmarking Bear Video
    if service_bear:
        print("\nBenchmarking Online Video (Bear)...")
        for bq in bear_queries:
            q = bq["query"]
            # Warmup
            _ = service_bear.search(query=q, top_k=5, use_llm=False, extract_clips=False)
            
            latencies = []
            similarities = []
            for _ in range(5):
                t0 = time.time()
                res = service_bear.search(query=q, top_k=3, use_llm=False, extract_clips=False)
                latencies.append((time.time() - t0) * 1000)
            
            results = res.get("results", [])
            for r in results:
                similarities.append(r["similarity"])
                
            avg_lat = np.mean(latencies)
            max_sim = similarities[0] if similarities else 0.0
            
            print(f"- Query: '{q}' | Latency: {avg_lat:.2f}ms | Top Match Similarity: {max_sim:.1f}%")
            benchmark_data.append({
                "query": q,
                "dataset": "Bear (Online)",
                "category": bq["category"],
                "latency": avg_lat,
                "top_similarity": max_sim,
                "all_similarities": similarities
            })

    # Ensure output paths exist
    os.makedirs(artifact_dir, exist_ok=True)
    
    # 2. Render Graph 1: Query Latency vs. 100ms SLA
    print("\n[INFO] Plotting latency breakdown graph...")
    plt.figure(figsize=(10, 6))
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    
    queries = [f"{d['query']}\n({d['dataset']})" for d in benchmark_data]
    latencies = [d["latency"] for d in benchmark_data]
    
    # Dynamic bar coloring: blue for successful categories, orange for fallback
    colors = ['#0284c7' if "Fallback" not in d["category"] else '#ea580c' for d in benchmark_data]
    
    bars = plt.barh(queries, latencies, color=colors, height=0.55, edgecolor='#1e293b', alpha=0.95)
    
    # SLA threshold line
    plt.axvline(x=100.0, color='#e11d48', linestyle='--', linewidth=2, label='100ms SLA Bound')
    
    # Add values on top of bars
    for bar in bars:
        width = bar.get_width()
        plt.text(width + 2, bar.get_y() + bar.get_height()/2, f'{width:.2f} ms', 
                 va='center', ha='left', fontsize=10, fontweight='bold', color='#1e293b')
        
    plt.xlabel('Execution Latency (milliseconds)', fontsize=12, fontweight='bold', labelpad=10)
    plt.title('Rawi-Vision Semantic Search Query Latency Benchmark', fontsize=14, fontweight='bold', pad=15)
    plt.xlim(0, 120)
    plt.gca().invert_yaxis()  # top-down query list
    plt.legend(loc='lower right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
    plt.tight_layout()
    
    latency_output_path = os.path.join(artifact_dir, "latency_breakdown.png")
    plt.savefig(latency_output_path, dpi=300)
    plt.close()
    print(f"[SUCCESS] Saved latency graph to: {latency_output_path}")

    # 3. Render Graph 2: Top Similarity Match Spread
    print("[INFO] Plotting similarity distribution graph...")
    plt.figure(figsize=(10, 6))
    
    # Filter out fallback queries for similarity graphs
    sim_data = [d for d in benchmark_data if "Fallback" not in d["category"]]
    
    queries_sim = [d["query"] for d in sim_data]
    sim_1st = [d["all_similarities"][0] if len(d["all_similarities"]) > 0 else 0.0 for d in sim_data]
    sim_2nd = [d["all_similarities"][1] if len(d["all_similarities"]) > 1 else 0.0 for d in sim_data]
    sim_3rd = [d["all_similarities"][2] if len(d["all_similarities"]) > 2 else 0.0 for d in sim_data]
    
    x = np.arange(len(queries_sim))
    width = 0.25
    
    rects1 = plt.bar(x - width, sim_1st, width, label='1st Best Match', color='#15803d', edgecolor='#166534')
    rects2 = plt.bar(x, sim_2nd, width, label='2nd Best Match', color='#16a34a', edgecolor='#15803d', alpha=0.75)
    rects3 = plt.bar(x + width, sim_3rd, width, label='3rd Best Match', color='#86efac', edgecolor='#22c55e', alpha=0.6)
    
    plt.ylabel('Cosine Semantic Similarity Match (%)', fontsize=12, fontweight='bold', labelpad=10)
    plt.title('Rawi-Vision Multimodal Match Similarity Score Distribution', fontsize=14, fontweight='bold', pad=15)
    plt.xticks(x, queries_sim, rotation=15, ha='right', fontsize=10, fontweight='bold')
    plt.ylim(0, 100)
    plt.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
    
    # Draw a matching boundary line
    plt.axhline(y=20.0, color='#64748b', linestyle=':', linewidth=1.5, label='Match Threshold (20%)')
    
    # Put similarity percentages on top of 1st best bars
    for rect in rects1:
        height = rect.get_height()
        plt.annotate(f'{height:.1f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold', color='#14532d')
                    
    plt.tight_layout()
    similarity_output_path = os.path.join(artifact_dir, "similarity_distribution.png")
    plt.savefig(similarity_output_path, dpi=300)
    plt.close()
    print(f"[SUCCESS] Saved similarity distribution graph to: {similarity_output_path}")

    print("=" * 80)
    print("  GRAPH GENERATION COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, help="Directory to save generated visual graphs")
    args = parser.parse_args()
    generate_graphs(args.artifact_dir)
    
    # Automatically run systematic accuracy, baseline comparison, and SNR contrast benchmarks
    try:
        from test.run_systematic_evaluation import run_systematic_benchmark
        run_systematic_benchmark(args.artifact_dir)
    except Exception as e:
        print(f"[WARN] Failed to run systematic evaluation integration: {e}")
