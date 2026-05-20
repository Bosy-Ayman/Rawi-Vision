#!/usr/bin/env python3
"""
Rawi-Vision Multi-Video End-to-End Test Suite
----------------------------------------------
Downloads (if needed) and evaluates the full offline → online search pipeline
across 4 diverse test videos, reporting metrics for each.

Usage:
  python test/run_video_evaluation.py
"""

import os
import sys
import json
import time
import sqlite3
import shutil
import tempfile
import subprocess
from pathlib import Path

# Set offline mode (use cached weights)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Add project root so imports work from test/ or ai/search/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.online_search import VideoSearchService


# ─────────────────────────────────────────────────────────────────────────────
# Test definitions – one entry per test video
# ─────────────────────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": "video1_store",
        "label": "Retail Store Aisle",
        "path": "videos/test_videos/video1_store.mp4",
        "db":    "videos/test_videos/video1_store.db",
        "faiss": "videos/test_videos/video1_store.faiss",
        "map":   "videos/test_videos/video1_store.json",
        "sampling": 16,
        "positive_queries": ["person", "store", "aisle"],
        "negative_queries": ["airplane", "ocean"],
    },
    {
        "id": "video2_street",
        "label": "Street Pedestrian Scene",
        "path": "videos/test_videos/video2_street.mp4",
        "db":    "videos/test_videos/video2_street.db",
        "faiss": "videos/test_videos/video2_street.faiss",
        "map":   "videos/test_videos/video2_street.json",
        "sampling": 16,
        "positive_queries": ["person", "walking", "street"],
        "negative_queries": ["submarine", "volcano"],
    },
    {
        "id": "video3_parking",
        "label": "Parking Lot",
        "path": "videos/test_videos/video3_parking.mp4",
        "db":    "videos/test_videos/video3_parking.db",
        "faiss": "videos/test_videos/video3_parking.faiss",
        "map":   "videos/test_videos/video3_parking.json",
        "sampling": 16,
        "positive_queries": ["car", "vehicle", "parking"],
        "negative_queries": ["ocean", "forest"],
    },
    {
        "id": "video4_office",
        "label": "Office/Corridor Scene",
        "path": "videos/test_videos/video4_office.mp4",
        "db":    "videos/test_videos/video4_office.db",
        "faiss": "videos/test_videos/video4_office.faiss",
        "map":   "videos/test_videos/video4_office.json",
        "sampling": 16,
        "positive_queries": ["person", "walking", "corridor"],
        "negative_queries": ["beach", "mountain"],
    },
]

PYTHON = sys.executable
INDEXER = str(Path(__file__).resolve().parent.parent / "core" / "offline_index.py")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def index_video(tc: dict) -> bool:
    """Run offline indexer on the video if the DB doesn't already exist."""
    if Path(tc["db"]).exists() and Path(tc["faiss"]).exists():
        print(f"  [SKIP] Index already exists for {tc['id']}")
        return True

    video_path = tc["path"]
    if not Path(video_path).exists():
        print(f"  [SKIP] Video not found: {video_path}  — skipping this case.")
        return False

    print(f"  [INDEX] Indexing {tc['label']} ({video_path})...")
    cmd = [
        PYTHON, INDEXER,
        video_path,
        "--sampling", str(tc["sampling"]),
        "--db",    tc["db"],
        "--faiss", tc["faiss"],
        "--map",   tc["map"],
    ]
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    elapsed = time.time() - t0

    if result.returncode == 0 and Path(tc["db"]).exists():
        # Count frames indexed
        with sqlite3.connect(tc["db"]) as conn:
            n = conn.execute("SELECT COUNT(*) FROM frames").fetchone()[0]
        print(f"  [OK] Indexed {n} frames in {elapsed:.1f}s")
        return True
    else:
        print(f"  [FAIL] Indexer returned exit code {result.returncode}")
        print(result.stdout[-600:])
        print(result.stderr[-600:])
        return False


def run_searches(tc: dict, service: VideoSearchService) -> dict:
    """Run all positive/negative search queries and collect stats."""
    results = {
        "positive": [],
        "negative": [],
        "latencies_ms": [],
    }

    # Positive queries – should return ≥1 result
    for q in tc["positive_queries"]:
        t0 = time.time()
        res = service.search(query=q, top_k=5, use_llm=False, extract_clips=False)
        lat = (time.time() - t0) * 1000
        found = res.get("total_results", 0) > 0
        results["positive"].append({"query": q, "found": found, "results": res.get("total_results", 0)})
        results["latencies_ms"].append(lat)
        status = "PASS" if found else "FAIL"
        print(f"    [{status}] '{q}' -> {res.get('total_results',0)} result(s)  ({lat:.0f}ms)")

    # Negative queries – should return 0 results
    for q in tc["negative_queries"]:
        t0 = time.time()
        res = service.search(query=q, top_k=5, use_llm=False, extract_clips=False)
        lat = (time.time() - t0) * 1000
        no_results = res.get("total_results", 0) == 0
        results["negative"].append({"query": q, "correct_zero": no_results, "results": res.get("total_results", 0)})
        results["latencies_ms"].append(lat)
        status = "PASS" if no_results else "FAIL"
        print(f"    [{status}] '{q}' (expect 0) -> {res.get('total_results',0)} result(s)  ({lat:.0f}ms)")

    return results


def evaluate_case(tc: dict) -> dict | None:
    section(f"Evaluating: {tc['label']} ({tc['id']})")

    # 1. Index
    ok = index_video(tc)
    if not ok:
        return None

    # 2. Load search service
    try:
        service = VideoSearchService(
            db_path=tc["db"],
            faiss_path=tc["faiss"],
            map_path=tc["map"],
            use_llm=False,
        )
    except Exception as e:
        print(f"  [FAIL] Could not load search service: {e}")
        return None

    # 3. Run searches
    print("\n  Search Results:")
    sr = run_searches(tc, service)
    del service  # release DB handles

    # 4. Compute metrics
    pos_pass = sum(1 for r in sr["positive"] if r["found"])
    neg_pass = sum(1 for r in sr["negative"] if r["correct_zero"])
    total = len(sr["positive"]) + len(sr["negative"])
    passed = pos_pass + neg_pass
    accuracy = passed / total * 100 if total else 0
    avg_lat = sum(sr["latencies_ms"]) / len(sr["latencies_ms"]) if sr["latencies_ms"] else 0

    print(f"\n  Accuracy: {accuracy:.1f}%  |  Avg latency: {avg_lat:.0f}ms")

    return {
        "id": tc["id"],
        "label": tc["label"],
        "accuracy_pct": accuracy,
        "passed": passed,
        "total": total,
        "avg_latency_ms": avg_lat,
        "positive_results": sr["positive"],
        "negative_results": sr["negative"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    header("Rawi-Vision Multi-Video End-to-End Evaluation")
    print(f"Using Python:  {PYTHON}")
    print(f"Using indexer: {INDEXER}")

    all_results = []
    skipped = []

    for tc in TEST_CASES:
        result = evaluate_case(tc)
        if result is None:
            skipped.append(tc["id"])
        else:
            all_results.append(result)

    # ─── Summary Dashboard ───────────────────────────────────────────────────
    header("Multi-Video Evaluation Summary Dashboard")

    if not all_results:
        print("No videos were evaluated (all skipped – check downloads).")
        return

    fmt_head = f"{'Video':<28} | {'Accuracy':>9} | {'Passed':>7} | {'Lat (ms)':>10}"
    print(fmt_head)
    print("-" * len(fmt_head))
    total_acc = 0
    for r in all_results:
        print(f"{r['label']:<28} | {r['accuracy_pct']:>8.1f}% | {r['passed']:>3}/{r['total']:<3} | {r['avg_latency_ms']:>8.0f}ms")
        total_acc += r["accuracy_pct"]

    overall = total_acc / len(all_results)
    print("-" * len(fmt_head))
    print(f"{'OVERALL AVERAGE':<28} | {overall:>8.1f}% | {'':>7} |")

    if skipped:
        print(f"\n[WARN] Skipped ({len(skipped)}): {', '.join(skipped)}  (video file not found)")

    # Save JSON report
    report_path = Path("videos/test_videos/evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[REPORT] Full report saved to: {report_path}")

    header("All Done" if not skipped else "Partial Evaluation Complete")
    if overall >= 80:
        print("  [OK] System is performing well across all evaluated videos!")
    elif overall >= 60:
        print("  [WARN] Moderate accuracy -- consider reindexing with lower sampling rate.")
    else:
        print("  [FAIL] Low accuracy -- check video quality or indexing parameters.")


if __name__ == "__main__":
    main()
