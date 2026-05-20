#!/usr/bin/env python3
"""
Download 4 diverse test videos from YouTube for comprehensive pipeline evaluation.

Videos chosen to cover different search scenarios:
  1. Retail/Store aisle – people browsing shelves (object detection, person tracking)
  2. Pedestrian street scene – people walking (motion analysis, OCR on signs)
  3. Parking lot – vehicles + people (multi-object YOLO, motion vectors)
  4. Office corridor – person walking, door interactions (ReID, activity)
"""

import subprocess
import sys
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "videos" / "test_videos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 4 diverse test videos with their expected content tags for later search validation
VIDEOS = [
    {
        "id": "video1_store",
        "url": "https://www.youtube.com/watch?v=v5-D5_KhLbI",  # CCTV Camera sample test video
        "label": "Retail store aisle – person browsing chips and snacks",
        "search_queries": ["person", "store", "aisle", "chips"],
    },
    {
        "id": "video2_street",
        "url": "https://www.youtube.com/watch?v=TdtMc9_KxY8",  # People walking street
        "label": "Street pedestrian scene – people walking on sidewalk",
        "search_queries": ["person walking", "street", "sidewalk"],
    },
    {
        "id": "video3_parking",
        "url": "https://www.youtube.com/watch?v=LV7RGiRQkqM",  # Parking lot surveillance
        "label": "Parking lot surveillance – car and person movement",
        "search_queries": ["car", "parking", "person", "vehicle"],
    },
    {
        "id": "video4_office",
        "url": "https://www.youtube.com/watch?v=3JZ_D3ELwOQ",  # Office/corridor footage
        "label": "Office corridor – person walking, door activity",
        "search_queries": ["person", "corridor", "walking", "door"],
    },
]

YT_DLP = str(Path(sys.executable).parent / "yt-dlp.exe")


def download_video(video_info):
    url = video_info["url"]
    vid_id = video_info["id"]
    out_path = OUTPUT_DIR / f"{vid_id}.mp4"

    if out_path.exists():
        print(f"[SKIP] Already downloaded: {out_path.name}")
        return str(out_path)

    print(f"\n[DOWNLOAD] {vid_id}: {video_info['label']}")
    print(f"  URL: {url}")

    cmd = [
        YT_DLP,
        "--format", "mp4[height<=720][ext=mp4]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--max-filesize", "150M",
        "--output", str(out_path),
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and out_path.exists():
            size_mb = out_path.stat().st_size / (1024 * 1024)
            print(f"  [SUCCESS] Downloaded {out_path.name} ({size_mb:.1f} MB)")
            return str(out_path)
        else:
            print(f"  [FAIL] yt-dlp failed for {vid_id}")
            print(f"  STDOUT: {result.stdout[-500:]}")
            print(f"  STDERR: {result.stderr[-500:]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"  [FAIL] Download timed out for {vid_id}")
        return None
    except Exception as e:
        print(f"  [FAIL] Exception: {e}")
        return None


def main():
    print("=" * 70)
    print("  RAWI-VISION TEST VIDEO DOWNLOADER")
    print("=" * 70)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Using yt-dlp: {YT_DLP}")

    if not Path(YT_DLP).exists():
        print(f"[ERROR] yt-dlp not found at {YT_DLP}")
        sys.exit(1)

    downloaded = []
    failed = []

    for v in VIDEOS:
        path = download_video(v)
        if path:
            downloaded.append((v, path))
        else:
            failed.append(v)

    print("\n" + "=" * 70)
    print("  DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"Downloaded: {len(downloaded)}/{len(VIDEOS)}")
    for v, p in downloaded:
        size = Path(p).stat().st_size / (1024 * 1024)
        print(f"  ✓ {v['id']}: {Path(p).name} ({size:.1f} MB)")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for v in failed:
            print(f"  ✗ {v['id']}: {v['url']}")
    print("=" * 70)

    # Write manifest
    manifest_path = OUTPUT_DIR / "test_manifest.txt"
    with open(manifest_path, "w") as f:
        f.write("# Test Video Manifest\n")
        for v, p in downloaded:
            f.write(f"{v['id']}|{p}|{v['label']}|{','.join(v['search_queries'])}\n")
    print(f"\nManifest saved to: {manifest_path}")


if __name__ == "__main__":
    main()
