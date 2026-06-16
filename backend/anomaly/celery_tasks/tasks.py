import re
import cv2
import time
import numpy as np
from collections import deque
import base64
import json
import os
from utils.celery_client import celery_app
from utils.model_cache import get_smolvlm, get_videomae, get_cache_status
from camera_ingestion.utils.redis import redis_client

# -------------------------- Config -------------------------------------------
STAGE1_MODEL_ID = "Nikeytas/videomae-crime-detector-fixed-format"
STAGE1_ANOMALY_IDX = 1
STAGE1_THRESHOLD = 0.55

STAGE3_MODEL_ID = "HuggingFaceTB/SmolVLM-Instruct"
STAGE3_COOLDOWN = 5.0
STAGE3_MAX_TOKENS = 35
STAGE3_NUM_BEAMS = 1

VIDEO_WINDOW = 16
FRAME_SIZE = (224, 224)
INFER_EVERY_N = 90

KAFKA_BROKER = "localhost:29092"
KAFKA_TOPIC = "anomaly-incidents"

# Task routing - dedicated queue for anomaly detection
celery_app.conf.task_routes = {
    "anomaly.celery_tasks.tasks.run_anomaly_detection": {"queue": "anomaly"},
}

# Global model state (now uses model_cache)
_models_loaded = False
torch = None
DEVICE = "cpu"

# -------------------------- Helpers ---------------------------------------

def publish_incident_event(frame_rgb, anomaly_type: str, description: str, confidence_score: float, camera_id: str):
    if _kafka_producer is None: return
    try:
        _, buffer = cv2.imencode(".jpg", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
        image_b64 = base64.b64encode(buffer).decode("utf-8")
        event = {
            "anomaly_type": anomaly_type,
            "description": description,
            "confidence_score": confidence_score,
            "camera_id": camera_id,
            "image_b64": image_b64,
        }
        _kafka_producer.produce(KAFKA_TOPIC, key="anomaly", value=json.dumps(event).encode("utf-8"))
        _kafka_producer.poll(0)
    except Exception as e:
        print(f"[Kafka] Publish failed: {e}")

def extract_anomaly_type(vlm_text: str) -> str:
    match = re.search(r'\[(\w+)\]', vlm_text)
    if match:
        atype = match.group(1).lower()
        if atype in ["violence", "theft", "trespassing", "vandalism", "unusual_behavior", "normal"]:
            return atype
    return "unknown"

def run_videomae(frames):
    """Run VideoMAE model for anomaly detection (uses cached model)."""
    import torch as _torch
    videomae_processor, videomae_model = get_videomae()
    device = "cuda" if _torch.cuda.is_available() else "cpu"
    inputs = videomae_processor(images=frames, return_tensors="pt").to(device)
    with _torch.no_grad():
        outputs = videomae_model(**inputs)
    return _torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

def sharpest_frame(frames):
    scores = []   
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
        score = cv2.Laplacian(gray, cv2.CV_64F).var()
        scores.append(score)
    return frames[np.argmax(scores)]

# -------------------------- The Celery Task -------------------------------

@celery_app.task(name="run_anomaly_detection", queue="anomaly")
def run_anomaly_detection(rtsp_url: str, camera_mac: str, task_id: str, is_live: bool = True):
    """
    Anomaly detection task using CACHED models to save memory.
    - Stage 1: VideoMAE (cached)
    - Stage 3: SmolVLM (cached, shared with indexing)
    """
    from PIL import Image
    import torch as _torch

    global _models_loaded, torch, DEVICE

    if not _models_loaded:
        print("[Anomaly] Loading models from cache...")
        torch = _torch
        DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[Anomaly] Using device: {DEVICE}")
        print(f"[Anomaly] Cached models: {get_cache_status()}")
        _models_loaded = True

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"Error: Could not open stream {rtsp_url}")
        return

    frame_buffer = deque(maxlen=VIDEO_WINDOW)
    vlm_frame_buffer = deque(maxlen=VIDEO_WINDOW)
    frame_count = 0
    last_vlm_time = 0

    print(f"Starting Anomaly Detection for {camera_mac} on {rtsp_url}")

    try:
        while True:
            if redis_client.get(f"stop_anomaly:{task_id}"):
                print(f"Stop signal received for task {task_id}")
                break

            ret, frame = cap.read()
            if not ret:
                if not is_live:
                    print(f"End of uploaded video file reached for task {task_id}")
                    break
                else:
                    cap.release()
                    time.sleep(5)
                    cap = cv2.VideoCapture(rtsp_url)
                    if not cap.isOpened(): break
                    continue

            frame_count += 1
            small_rgb = cv2.cvtColor(cv2.resize(frame, FRAME_SIZE), cv2.COLOR_BGR2RGB)
            full_rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_buffer.append(small_rgb)
            vlm_frame_buffer.append(full_rgb)

            if frame_count % INFER_EVERY_N == 0 and len(frame_buffer) == VIDEO_WINDOW:
                s1_probs = run_videomae(list(frame_buffer))
                s1_score = s1_probs[STAGE1_ANOMALY_IDX].item()

                print(f"[Heartbeat] Background check complete -> Anomaly Score: {s1_score:.4f} (Threshold: {STAGE1_THRESHOLD})")

                if s1_score > STAGE1_THRESHOLD:
                    now = time.time()
                    if (now - last_vlm_time) > STAGE3_COOLDOWN:
                        snap = sharpest_frame(list(vlm_frame_buffer))
                        pil_img = Image.fromarray(snap)

                        # Get cached SmolVLM (shared with indexing!)
                        s3_processor, s3_model = get_smolvlm()

                        # Ask the VLM to explain the scene
                        prompt = "First, describe any human activity in this surveillance frame in detail (ignore watermarks). Second, classify the activity by appending exactly one of these tags at the end: [normal], [violence], [theft], [trespassing], [vandalism], or [unusual_behavior]. If no crime is occurring, use [normal]."
                        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
                        text_input = s3_processor.apply_chat_template(messages, add_generation_prompt=True)
                        inputs = s3_processor(images=[pil_img], text=text_input, return_tensors="pt").to(DEVICE)

                        with torch.no_grad():
                            out = s3_model.generate(**inputs, max_new_tokens=STAGE3_MAX_TOKENS)

                        raw = s3_processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                        anomaly_type = extract_anomaly_type(raw)

                        # Publish the explanation to dashboard
                        print(f"!!! SCENE EXPLANATION: {raw}")
                        publish_incident_event(snap, anomaly_type, raw, s1_score, camera_mac)
                        last_vlm_time = now

            time.sleep(0.01)

    finally:
        cap.release()
        print(f"Anomaly Detection task {task_id} finished.")
