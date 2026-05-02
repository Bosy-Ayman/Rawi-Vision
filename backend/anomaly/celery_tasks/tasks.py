import re
import cv2
import time
import numpy as np
from collections import deque
import base64
import json
import os
from utils.celery_client import celery_app
from camera_ingestion.utils.redis import redis_client

# -------------------------- Config -------------------------------------------
STAGE1_MODEL_ID = "Nikeytas/videomae-crime-detector-fixed-format"
STAGE1_ANOMALY_IDX = 1
STAGE1_THRESHOLD = 0.5

STAGE3_MODEL_ID = "HuggingFaceTB/SmolVLM-Instruct"
STAGE3_COOLDOWN = 5.0
STAGE3_MAX_TOKENS = 35
STAGE3_NUM_BEAMS = 1

VIDEO_WINDOW = 16
FRAME_SIZE = (224, 224)
INFER_EVERY_N = 16

KAFKA_BROKER = "localhost:29092"
KAFKA_TOPIC = "anomaly-incidents"

# -------------------------- Global Model Instances (Lazy) -------------------------------
s1_processor = None
s1_model = None
s3_processor = None
s3_model = None
_kafka_producer = None
torch = None
DEVICE = "cpu"

def load_models():
    """Heavy imports and model loading happen ONLY when this is called."""
    global s1_processor, s1_model, s3_processor, s3_model, _kafka_producer, torch, DEVICE
    
    if s1_model is not None:
        return

    # Heavy Imports (Inside function to save memory)
    import torch as _torch
    torch = _torch
    from transformers import (
        AutoModelForVideoClassification,
        AutoImageProcessor,
        AutoProcessor,
        AutoModelForVision2Seq,
        BitsAndBytesConfig,
    )
    from confluent_kafka import Producer as KafkaProducer

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading Anomaly Models on {DEVICE}...")

    s1_processor = AutoImageProcessor.from_pretrained(STAGE1_MODEL_ID)
    s1_model = AutoModelForVideoClassification.from_pretrained(STAGE1_MODEL_ID).to(DEVICE).eval()

    s3_processor = AutoProcessor.from_pretrained(STAGE3_MODEL_ID)
    s3_model = AutoModelForVision2Seq.from_pretrained(
        STAGE3_MODEL_ID,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        ),
        device_map="auto",
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
        attn_implementation="eager",
    ).eval()

    try:
        _kafka_producer = KafkaProducer({"bootstrap.servers": KAFKA_BROKER})
        print(f"[Kafka] Producer connected to {KAFKA_BROKER}")
    except Exception as e:
        print(f"[Kafka] Producer init failed: {e}")

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
    inputs = s1_processor(images=frames, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = s1_model(**inputs)
    return torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

def sharpest_frame(frames):
    scores = []   
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
        score = cv2.Laplacian(gray, cv2.CV_64F).var()
        scores.append(score)
    return frames[np.argmax(scores)]

# -------------------------- The Celery Task -------------------------------

@celery_app.task(name="run_anomaly_detection")
def run_anomaly_detection(rtsp_url: str, camera_mac: str, task_id: str):
    load_models()
    from PIL import Image # Local import
    
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
                
                if s1_score > STAGE1_THRESHOLD:
                    now = time.time()
                    if (now - last_vlm_time) > STAGE3_COOLDOWN:
                        snap = sharpest_frame(list(vlm_frame_buffer))
                        pil_img = Image.fromarray(snap)
                        
                        prompt = "Detect and classify the anomaly in this surveillance frame. Output format: [ANOMALY_TYPE] Brief description."
                        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
                        text_input = s3_processor.apply_chat_template(messages, add_generation_prompt=True)
                        inputs = s3_processor(images=[pil_img], text=text_input, return_tensors="pt").to(DEVICE)

                        with torch.no_grad():
                            out = s3_model.generate(**inputs, max_new_tokens=STAGE3_MAX_TOKENS)
                        
                        raw = s3_processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                        anomaly_type = extract_anomaly_type(raw)
                        print(f"!!! ANOMALY DETECTED [{anomaly_type}]: {raw}")
                        publish_incident_event(snap, anomaly_type, raw, s1_score, camera_mac)
                        last_vlm_time = now

            time.sleep(0.01)

    finally:
        cap.release()
        print(f"Anomaly Detection task {task_id} finished.")
