#!/usr/bin/env python3
"""
Rawi-Vision Online Video Evaluation Tool
----------------------------------------
This utility downloads a video from a public URL, indexes it frame-by-frame 
using YOLOv8 and SmolVLM directly on the GPU, and allows running semantic RAG 
queries to evaluate pipeline performance.
"""

import os
import sys
import time
import urllib.request
import argparse
from pathlib import Path

# Resolve import paths to peer core/ directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

IMPORTS_OK = True

DEFAULT_VIDEO_URL = "https://www.w3schools.com/html/movie.mp4"
DEFAULT_QUERIES = ["bear or animal in water", "splashing water", "wild brown bear", "green grass or trees"]

def download_video(url: str, output_path: Path):
    print(f"\n[INFO] Downloading online video from:\n  {url}")
    print(f"[INFO] Saving to: {output_path}...")
    
    start_time = time.time()
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
            total_size = int(response.info().get('Content-Length', 0))
            read_so_far = 0
            block_size = 8192
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                read_so_far += len(buffer)
                out_file.write(buffer)
                if total_size > 0:
                    percent = min(100, (read_so_far * 100) / total_size)
                    sys.stdout.write(f"\r  Downloading: {percent:.1f}% ({read_so_far / (1024*1024):.2f}MB / {total_size / (1024*1024):.2f}MB)")
                else:
                    sys.stdout.write(f"\r  Downloading: {read_so_far / (1024*1024):.2f}MB")
                sys.stdout.flush()
        
        elapsed = time.time() - start_time
        print(f"\n[SUCCESS] Download completed in {elapsed:.2f} seconds.")
    except Exception as e:
        print(f"\n[ERROR] Failed to download video: {e}")
        sys.exit(1)

def run_pipeline_evaluation(video_url: str, sampling: int, query: str):
    import gc
    import torch

    # Define temporary files for online evaluation
    online_dir = Path("online_eval")
    online_dir.mkdir(exist_ok=True)

    video_path = online_dir / "eval_video.mp4"
    db_path = online_dir / "online_video.db"
    faiss_path = online_dir / "online_video.faiss"
    map_path = online_dir / "online_video.json"

    # Step 1: Download Video
    download_video(video_url, video_path)

    # Step 2: Index Video using VLM and YOLO
    print("\n" + "=" * 80)
    print("  STEP 2: RUNNING OFFLINE INDEXING (YOLOv8 + SmolVLM)")
    print("=" * 80)
    print(f"[INFO] Output Database: {db_path}")
    print(f"[INFO] Output FAISS Index: {faiss_path}")
    
    # Remove existing files if they exist to ensure clean state
    for p in [db_path, faiss_path, map_path]:
        if p.exists():
            p.unlink()

    # Dynamic import to minimize baseline memory footprint during VLM/YOLO loading
    from core.offline_index import index_video

    start_idx = time.time()
    try:
        index_video(
            source=str(video_path),
            sampling=sampling,
            db_path=str(db_path),
            faiss_path=str(faiss_path),
            map_path=str(map_path)
        )
        print(f"[SUCCESS] Indexing completed in {time.time() - start_idx:.2f} seconds.")
    except Exception as e:
        print(f"[ERROR] Indexing failed: {e}")
        return

    # Free up memory and empty PyTorch CUDA cache prior to starting the search service
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # Step 3: Initialize Video Search Service and Evaluate Queries
    print("\n" + "=" * 80)
    print("  STEP 3: RUNNING SEMANTIC SEARCH EVALUATION")
    print("=" * 80)
    
    from core.online_search import VideoSearchService
    try:
        service = VideoSearchService(
            db_path=str(db_path),
            faiss_path=str(faiss_path),
            map_path=str(map_path),
            use_llm=True,
            llm_model_name="Qwen/Qwen2.5-0.5B-Instruct"
        )
    except Exception as e:
        print(f"[ERROR] Failed to initialize search service: {e}")
        return

    queries_to_test = [query] if query else DEFAULT_QUERIES
    
    for q in queries_to_test:
        print(f"\n👉 Evaluating Query: '{q}'...")
        t0 = time.time()
        res = service.search(
            query=q,
            top_k=3,
            use_llm=True,
            video_path=str(video_path),
            extract_clips=True,
            clip_duration=6.0,
            clips_dir=str(online_dir / "clips")
        )
        latency = (time.time() - t0) * 1000
        
        print(f"⏱️ Search finished in {latency:.2f} ms")
        print("-" * 50)
        print(f"📝 LLM Synthesis:\n{res.get('llm_answer', 'No LLM answer')}")
        print("-" * 50)
        print("🔍 Top matches:")
        for r in res.get("results", []):
            print(f"  - Frame {r['frame_id']} ({r['timestamp']:.2f}s) [Similarity: {r['similarity']}%]")
            print(f"    Description: {r['description'][:140]}...")
            if r.get("clip_path"):
                print(f"    Clip saved to: {r['clip_path']}")
        print("=" * 80)

    print(f"\n🎉 Online video evaluation successfully executed!")
    print(f"📁 All files saved in: {online_dir.resolve()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the Rawi-Vision pipeline with an online video URL")
    parser.add_argument("--url", default=DEFAULT_VIDEO_URL, help="URL of the video to index and evaluate")
    parser.add_argument("--sampling", type=int, default=30, help="Sample every N-th frame for indexing")
    parser.add_argument("--query", default="", help="Custom semantic query to search. If omitted, runs default suite.")
    args = parser.parse_args()

    run_pipeline_evaluation(args.url, args.sampling, args.query)
