import cv2
import glob
import os
import subprocess
import shutil
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def _stamp_frame(frame, cam_id: str, frame_idx: int):
    annotated = frame.copy()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    text = f"{cam_id} | frame {frame_idx} | {now}"
    cv2.putText(
        annotated, text, (8, annotated.shape[0] - 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA,
    )
    return annotated


def _encode_with_ffmpeg(
    frame_pattern: str,
    output_path: str,
    fps: int,
    crf: int = 23,
) -> bool:
   
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-pattern_type", "glob",
        "-i", frame_pattern,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", 
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("ffmpeg encoding succeeded (H.264)")
            return True
        logger.warning(
            f"ffmpeg returned code {result.returncode}: "
            f"{result.stderr.decode()[-200:]}"
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"ffmpeg unavailable or timed out ({exc}) – using OpenCV")
    return False


def _encode_with_opencv(
    frames: list,
    output_path: str,
    fps: int,
    cam_id: str,
    codec: str = "mp4v",
):
    first_img = None
    for f in frames:
        img = cv2.imread(f)
        if img is not None:
            first_img = img
            break

    if first_img is None:
        logger.error("No valid images found – cannot create video")
        return 0

    h, w = first_img.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    count = 0
    for idx, f in enumerate(frames):
        img = cv2.imread(f)
        if img is None:
            continue
        stamped = _stamp_frame(img, cam_id, idx)
        writer.write(stamped)
        count += 1

    writer.release()
    return count



def frames_to_video(
    frames_dir: str,
    output_path: str,
    fps: int = 12,
    cam_id: str = "cam",
    codec: str = "mp4v",
    crf: int = 23,
):
 
    frames = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))

    if not frames:
        logger.warning(f"[{cam_id}] No frames found in {frames_dir}")
        return

    logger.info(f"[{cam_id}] Encoding {len(frames)} frames to {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    t_start = time.time()
    count = len(frames)
    success = False

    if shutil.which("ffmpeg"):
        frame_pattern = os.path.join(frames_dir, "*.jpg")
        success = _encode_with_ffmpeg(frame_pattern, output_path, fps, crf)

    if not success:
        count = _encode_with_opencv(frames, output_path, fps, cam_id, codec)
        success = count > 0

    elapsed = time.time() - t_start

    if success and os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / 1e6
        logger.info(
            f"[{cam_id}] Video saved: {output_path} "
            f"({count} frames, {size_mb:.1f} MB, {elapsed:.1f}s)"
        )
    else:
        logger.error(f"[{cam_id}] Video encoding failed")
