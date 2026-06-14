import yaml
import os
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai.Summarization_Pipeline.camera_manager import CameraManager
from ai.Summarization_Pipeline.frame_processor import save_frame
from ai.Summarization_Pipeline.video_generator import frames_to_video
from ai.Summarization_Pipeline.object_detection import load_model, detect_and_filter
from ai.Summarization_Pipeline.utils import ensure_dir, setup_logging, compute_frame_skip, write_run_report
from ai.Summarization_Pipeline.motion_filter import MotionFilter

logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def process_camera(cam_id: str, cam_cfg: dict, settings: dict, model) -> dict:

    t_start = time.time()
    logger.info(f"\n{'─'*60}\n  Camera: {cam_id} – {cam_cfg.get('name','')}\n{'─'*60}")

    base_output    = settings["output_path"]
    selected_dir   = os.path.join(base_output, cam_id, "selected_frames")
    detected_dir   = os.path.join(base_output, cam_id, "detected_frames")
    summary_dir    = os.path.join(base_output, cam_id, "summaries")
    report_dir     = os.path.join(base_output, cam_id)

    for d in (selected_dir, detected_dir, summary_dir):
        ensure_dir(d)

    manager = CameraManager({cam_id: cam_cfg}, settings)

    import cv2
    sources = cam_cfg.get("sources", [])
    source_fps = 25.0
    total_frames_hint = 0
    if sources:
        cap = cv2.VideoCapture(sources[0]["path"])
        if cap.isOpened():
            source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames_hint = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()

    frame_skip = compute_frame_skip(
        total_frames=total_frames_hint if total_frames_hint > 0
                     else settings.get("max_frames_per_cam", 5000) * settings.get("frame_skip", 5),
        source_fps=source_fps,
        max_frames=settings.get("max_frames_per_cam", 5000),
        target_sample_fps=2.0,
    )

    motion = MotionFilter(
        threshold=settings.get("motion_threshold", 25),
        min_area=settings.get("motion_min_area", 800),
        adaptive=settings.get("adaptive_motion", True),
    )

    saved_id = 0
    total_seen = 0

    logger.info(f"[{cam_id}] Streaming with frame_skip={frame_skip} …")

    for global_id, frame, fps in manager.stream_frames(cam_id, frame_skip=frame_skip):
        total_seen += 1

        if motion.is_motion(frame):
            path = save_frame(
                base_output, cam_id, saved_id, frame,
                blur_faces=settings.get("blur_faces", True),
            )
            if path:
                saved_id += 1

        if saved_id >= settings.get("max_frames_per_cam", 5000):
            logger.warning(
                f"[{cam_id}] reached max_frames_per_cam={settings['max_frames_per_cam']} "
                f"– stopp early ,stream still had frames"
            )
            break

    logger.info(
        f"[{cam_id}] frames seen={total_seen}  motion saved={saved_id}"
    )

    detect_and_filter(
        frames_dir=selected_dir,
        output_dir=detected_dir,
        model=model,
        conf=settings.get("yolo_confidence", 0.5),
        allowed=settings.get("allowed_classes"),
        batch_size=settings.get("batch_size", 16),
        log_detections=settings.get("log_detections", True),
        cam_id=cam_id,
    )

    final_video = os.path.join(summary_dir, "final_summary.mp4")
    frames_to_video(
        frames_dir=detected_dir,
        output_path=final_video,
        fps=settings.get("summary_fps", 12),
        cam_id=cam_id,
        codec=settings.get("video_codec", "mp4v"),
        crf=settings.get("video_crf", 23),
    )

    elapsed = time.time() - t_start
    logger.info(f"[{cam_id}] Done in {elapsed:.1f}s\n")

    stats = {
        "total_frames_sampled": total_seen,
        "motion_frames": saved_id,
        "video_path": final_video,
        "duration_sec": round(elapsed, 1),
        "frame_skip_used": frame_skip,
    }
    write_run_report(report_dir, cam_id, stats)
    return stats



def main():
    setup_logging()
    config  = load_config()
    cams    = config["cameras"]
    settings = config["config"]

    logger.info("\n" + "═"*60)
    logger.info(" CCTV Summarization START")
    logger.info("═"*60)

   
    model = load_model(
        path=settings.get("model_path", "yolov8s.pt"),
        use_gpu=settings.get("use_gpu", True),
    )

    results = {}

    if settings.get("parallel_cameras", True) and len(cams) > 1:
        max_w = min(settings.get("max_workers", 4), len(cams))
        logger.info(f"Processing {len(cams)} cameras in parallel (workers={max_w})")

        with ThreadPoolExecutor(max_workers=max_w) as pool:
            futures = {
                pool.submit(
                    process_camera, cam_id, cam_cfg, settings, model
                ): cam_id
                for cam_id, cam_cfg in cams.items()
            }

            for future in as_completed(futures):
                cam_id = futures[future]
                try:
                    stats = future.result()
                    results[cam_id] = stats
                except Exception as exc:
                    logger.error(f"[{cam_id}] Pipeline failed: {exc}", exc_info=True)
                    results[cam_id] = {"error": str(exc)}
    else:
        logger.info(f"Process {len(cams)} cameras sequentially")
        for cam_id, cam_cfg in cams.items():
            try:
                results[cam_id] = process_camera(cam_id, cam_cfg, settings, model)
            except Exception as exc:
                logger.error(f"[{cam_id}] Pipeline failed: {exc}", exc_info=True)
                results[cam_id] = {"error": str(exc)}

    logger.info("\n" + "═"*60)
    logger.info("  ALL CAMERAS DONE ")
    logger.info("═"*60)
    for cam_id, stats in results.items():
        if "error" in stats:
            logger.error(f"  {cam_id}: failed – {stats['error']}")
        else:
            logger.info(
                f"  {cam_id}: {stats.get('motion_frames',0)} motion frames "
                f"→ {stats.get('video_path','?')} "
                f"({stats.get('duration_sec',0):.0f}s)"
            )
    logger.info("═"*60 + "\n")


if __name__ == "__main__":
    main()
