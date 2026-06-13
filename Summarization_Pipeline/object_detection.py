from ultralytics import YOLO
import cv2
import os
import glob
import json
import logging
import torch
import numpy as np
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_device(use_gpu: bool = True) -> str:

    if use_gpu:
        if torch.cuda.is_available():
            device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f" CUDA GPU detected: {gpu_name} ({vram_gb:.1f} GB VRAM)")
        elif torch.backends.mps.is_available():
            device = "mps"
            logger.info("Apple MPS detected")
        else:
            device = "cpu"
            logger.warning(
                "No GPU detected – falling back to CPU. "
                "Set use_gpu=false in config"
            )
    else:
        device = "cpu"

    logger.info(f"Inference device: {device.upper()}")
    return device


def load_model(path: str = "yolov8s.pt", use_gpu: bool = True) -> YOLO:
    logger.info(f"Loading YOLO model: {path}")
    device = get_device(use_gpu)
    model = YOLO(path)
    model.to(device)
    logger.info("YOLO is loaded")
    return model



def detect_and_filter(
    frames_dir: str,
    output_dir: str,
    model: YOLO,
    conf: float = 0.25,
    allowed: list = None,
    batch_size: int = 16,
    log_detections: bool = True,
    cam_id: str = "unknown",
):
  
    os.makedirs(output_dir, exist_ok=True)

    frames = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))
    total = len(frames)
    logger.info(f"[{cam_id}] Detecting on {total} frames  (batch={batch_size})")

    if total == 0:
        logger.warning(f"[{cam_id}] No frames found in {frames_dir}")
        return

    kept = 0
    det_log = []  

    conf_scores = []

    for batch_start in range(0, total, batch_size):
        batch_paths = frames[batch_start : batch_start + batch_size]

        try:
            results_batch = model(
                batch_paths,
                conf=conf,
                verbose=False,   
            )
        except Exception as exc:
            logger.error(
                f"[{cam_id}] YOLO inference failed on batch "
                f"[{batch_start}:{batch_start + batch_size}]: {exc}"
            )
            continue

        for path, result in zip(batch_paths, results_batch):
            frame_name = os.path.basename(path)
            img = cv2.imread(path)

            if img is None:
                logger.warning(f"[{cam_id}] can't read frame: {path}")
                continue

            valid = False
            frame_detections = []

            for box in result.boxes:
                cls_id = int(box.cls)
                name = result.names[cls_id]
                score = float(box.conf)

                conf_scores.append(score)

                if allowed and name not in allowed:
                    continue

                valid = True

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                label = f"{name} {score:.2f}"
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    img, label, (x1, max(y1 - 5, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
                )

                frame_detections.append({
                    "class": name,
                    "confidence": round(score, 3),
                    "bbox": [x1, y1, x2, y2],
                })

            if valid:
                out_path = os.path.join(output_dir, frame_name)
                cv2.imwrite(out_path, img)
                kept += 1

                if log_detections:
                    det_log.append({
                        "cam_id": cam_id,
                        "frame": frame_name,
                        "timestamp": datetime.utcnow().isoformat(),
                        "detections": frame_detections,
                    })

        processed_so_far = min(batch_start + batch_size, total)
        if processed_so_far % 200 == 0 or processed_so_far == total:
            logger.info(
                f"[{cam_id}] Progress: {processed_so_far}/{total}  "
                f"kept={kept}"
            )

    if log_detections and det_log:
        log_path = os.path.join(output_dir, "detections.jsonl")
        with open(log_path, "w") as f:
            for entry in det_log:
                f.write(json.dumps(entry) + "\n")
        logger.info(f"[{cam_id}] Detection log saved: {log_path}")

    if conf_scores:
        arr = np.array(conf_scores)
        logger.info(
            f"[{cam_id}] Confidence stats – "
            f"mean={arr.mean():.3f}  median={np.median(arr):.3f}  "
            f"min={arr.min():.3f}  max={arr.max():.3f}  n={len(arr)}"
        )

    logger.info(f"[{cam_id}] Kept {kept}/{total} frames after object filtering")
