"""
Standalone anomaly detection process (VideoMAE-only mode).

Run by the Celery task as a subprocess so that model loading happens in a
clean Python process with no thread pool conflicts.

SmolVLM scene description is intentionally disabled here because Windows
safetensors memory-mapping crashes when loading 2GB+ models in a subprocess.
The search indexer already has SmolVLM loaded in the main worker process —
anomaly detection uses VideoMAE (loaded on CUDA) for real-time scoring only.
"""
import re
import os
import sys
import json
import base64
import time

# Thread limits must be set FIRST, before any heavy library is imported
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["TQDM_DISABLE"] = "1"

import cv2
import numpy as np
import torch
from collections import deque
from transformers import AutoModelForVideoClassification, AutoImageProcessor

try:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
except RuntimeError:
    pass
try:
    cv2.setNumThreads(1)
except Exception:
    pass

# Add backend to sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from camera_ingestion.utils.redis import redis_client

# ---- Config ----
STAGE1_MODEL_ID = "Nikeytas/videomae-crime-detector-fixed-format"
STAGE1_ANOMALY_IDX = 1
STAGE1_THRESHOLD = 0.75 # Raised from 0.55 — VideoMAE scores ~0.67 on normal footage for this camera

VIDEO_WINDOW = 16
FRAME_SIZE = (224, 224)
INFER_EVERY_N = 90

KAFKA_BROKER = "localhost:29092"
KAFKA_TOPIC = "anomaly-incidents"


def decide_device():
    if torch.cuda.is_available() and torch.cuda.device_count() > 0:
        try:
            free_vram, _ = torch.cuda.mem_get_info()
        except Exception:
            free_vram = (
                torch.cuda.get_device_properties(0).total_memory
                - torch.cuda.memory_allocated(0)
            )
        if free_vram > 1.0 * 1024 ** 3:
            return "cuda"
        print(f"[Anomaly Worker] Low VRAM ({free_vram / 1024**3:.2f} GB) — using CPU", flush=True)
    return "cpu"


def publish_incident(kafka_producer, anomaly_score: float, camera_id: str):
    if kafka_producer is None:
        return
    try:
        event = {
            "anomaly_type": "unknown",  # valid AnomalyTypeEnum value
            "description": f"VideoMAE anomaly score: {anomaly_score:.4f} (threshold: {STAGE1_THRESHOLD})",
            "confidence_score": anomaly_score,
            "camera_id": camera_id,
        }
        kafka_producer.produce(KAFKA_TOPIC, key="anomaly", value=json.dumps(event).encode("utf-8"))
        kafka_producer.poll(0)
    except Exception as e:
        print(f"[Kafka] Publish failed: {e}", flush=True)


def main():
    if len(sys.argv) < 4:
        print("Usage: anomaly_worker.py <rtsp_url> <camera_mac> <task_id>", flush=True)
        sys.exit(1)

    rtsp_url = sys.argv[1]
    camera_mac = sys.argv[2]
    task_id = sys.argv[3]

    device = decide_device()
    print(f"[Anomaly Worker] Loading VideoMAE on {device}...", flush=True)

    s1_processor = AutoImageProcessor.from_pretrained(STAGE1_MODEL_ID)
    s1_model = AutoModelForVideoClassification.from_pretrained(
        STAGE1_MODEL_ID
    ).to(device).eval()
    print("[Anomaly Worker] VideoMAE loaded. Starting detection loop...", flush=True)

    # Optional Kafka
    kafka_producer = None
    try:
        from confluent_kafka import Producer as KafkaProducer
        kafka_producer = KafkaProducer({"bootstrap.servers": KAFKA_BROKER})
        print(f"[Kafka] Producer connected.", flush=True)
    except Exception as e:
        print(f"[Kafka] Unavailable: {e}", flush=True)

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"[Anomaly Worker] Error: Could not open stream {rtsp_url}", flush=True)
        sys.exit(1)

    frame_buffer = deque(maxlen=VIDEO_WINDOW)
    frame_count = 0
    last_alert_time = 0
    ALERT_COOLDOWN = 10.0  # seconds between Kafka publishes

    print(f"[Anomaly Worker] Detection active for camera {camera_mac}", flush=True)

    try:
        while True:
            if redis_client.get(f"stop_anomaly:{task_id}"):
                print("[Anomaly Worker] Stop signal received.", flush=True)
                break

            ret, frame = cap.read()
            if not ret:
                cap.release()
                time.sleep(5)
                cap = cv2.VideoCapture(rtsp_url)
                if not cap.isOpened():
                    print("[Anomaly Worker] Stream lost, exiting.", flush=True)
                    break
                continue

            frame_count += 1
            small_rgb = cv2.cvtColor(cv2.resize(frame, FRAME_SIZE), cv2.COLOR_BGR2RGB)
            frame_buffer.append(small_rgb)

            if frame_count % INFER_EVERY_N == 0 and len(frame_buffer) == VIDEO_WINDOW:
                inputs = s1_processor(
                    images=list(frame_buffer), return_tensors="pt"
                ).to(device)
                with torch.no_grad():
                    outputs = s1_model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]
                score = probs[STAGE1_ANOMALY_IDX].item()

                if score > STAGE1_THRESHOLD:
                    print(
                        f"[Anomaly Heartbeat] *** ANOMALY DETECTED *** "
                        f"Score: {score:.4f} / {STAGE1_THRESHOLD} | Camera: {camera_mac}",
                        flush=True,
                    )
                    now = time.time()
                    if (now - last_alert_time) > ALERT_COOLDOWN:
                        publish_incident(kafka_producer, score, camera_mac)
                        last_alert_time = now
                else:
                    print(
                        f"[Anomaly Heartbeat] Normal "
                        f"Score: {score:.4f} / {STAGE1_THRESHOLD} | Camera: {camera_mac}",
                        flush=True,
                    )

            time.sleep(0.01)

    finally:
        cap.release()
        print(f"[Anomaly Worker] Finished.", flush=True)


if __name__ == "__main__":
    main()
