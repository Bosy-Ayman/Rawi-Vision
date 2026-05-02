import os
import logging
import json
from datetime import datetime
from pathlib import Path



def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def setup_logging(log_dir: str = "logs", level: int = logging.INFO):
  
    ensure_dir(log_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"pipeline_{ts}.log")

    fmt = "%(asctime)s [%(levelname)-8s] %(name)s – %(message)s"
    datefmt = "%H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    logging.info(f"Log file: {log_file}")



def compute_frame_skip(
    total_frames: int,
    source_fps: float,
    max_frames: int = 5000,
    target_sample_fps: float = 2.0,
) -> int:
   
    if source_fps <= 0:
        source_fps = 25.0

    # Skip to reach target_sample_fps
    fps_skip = max(1, int(source_fps / target_sample_fps))

    # additional skip to respect max_frames hard cap
    estimated_sampled = total_frames / fps_skip
    if estimated_sampled > max_frames:
        cap_skip = int(total_frames / max_frames)
    else:
        cap_skip = 1

    final_skip = max(fps_skip, cap_skip)

    logging.getLogger(__name__).info(
        f"Frame sampling: total={total_frames}  fps={source_fps:.1f}  "
        f"skip={final_skip}  estimated_samples={total_frames // final_skip}"
    )
    return final_skip



def write_run_report(
    output_dir: str,
    cam_id: str,
    stats: dict,
):
  
    ensure_dir(output_dir)
    report_path = os.path.join(output_dir, f"run_report_{cam_id}.json")
    stats["cam_id"] = cam_id
    stats["generated_at"] = datetime.utcnow().isoformat()

    with open(report_path, "w") as f:
        json.dump(stats, f, indent=2)

    logging.getLogger(__name__).info(f"Run report saved: {report_path}")
    return report_path
