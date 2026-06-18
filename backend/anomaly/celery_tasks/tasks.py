import re
import cv2
import time
import numpy as np
from collections import deque
import base64
import json

from utils.celery_client import celery_app
from camera_ingestion.utils.redis import redis_client

# -------------------------- Config -------------------------------------------
STAGE1_MODEL_ID = "Nikeytas/videomae-crime-detector-fixed-format"
STAGE1_ANOMALY_IDX = 1
STAGE1_THRESHOLD = 0.4

STAGE3_MODEL_ID = "HuggingFaceTB/SmolVLM-Instruct"
STAGE3_COOLDOWN = 5.0
STAGE3_MAX_TOKENS = 120

VIDEO_WINDOW = 16
FRAME_SIZE = (224, 224)
INFER_EVERY_N = 90

KAFKA_BROKER = "localhost:29092"
KAFKA_TOPIC = "anomaly-incidents"

VALID_LABELS = {
    "normal",
    "violence",
    "theft",
    "trespassing",
    "vandalism",
    "unusual_behavior"
}

# -------------------------- Globals -------------------------------------------
s1_processor = None
s1_model = None
s3_processor = None
s3_model = None
torch = None
DEVICE = "cpu"

_kafka_producer = None
kafka_enabled = False


# -------------------------- MODEL LOADING -------------------------------------
def load_models():
    global s1_processor, s1_model, s3_processor, s3_model
    global torch, DEVICE, _kafka_producer, kafka_enabled

    if s1_model is not None:
        return

    import torch as _torch
    torch = _torch

    from transformers import (
        AutoImageProcessor,
        AutoModelForVideoClassification,
        AutoProcessor,
        AutoModelForImageTextToText,
        BitsAndBytesConfig,
    )

    from confluent_kafka import Producer

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Loading models on {DEVICE}")

    s1_processor = AutoImageProcessor.from_pretrained(STAGE1_MODEL_ID)
    s1_model = AutoModelForVideoClassification.from_pretrained(
        STAGE1_MODEL_ID
    ).to(DEVICE).eval()

    s3_processor = AutoProcessor.from_pretrained(STAGE3_MODEL_ID)
    s3_model = AutoModelForImageTextToText.from_pretrained(
        STAGE3_MODEL_ID,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        ),
        device_map="auto",
        torch_dtype=torch.float16,
    ).eval()

    try:
        _kafka_producer = Producer({"bootstrap.servers": KAFKA_BROKER})
        kafka_enabled = True
        print("[INFO] Kafka connected")
    except Exception as e:
        kafka_enabled = False
        _kafka_producer = None
        print(f"[WARN] Kafka disabled: {e}")


# -------------------------- CLEANING ------------------------------------------
def clean_text(text: str) -> str:
    patterns = [
        r"camera\s*\d+",
        r"cam\s*\d+",
        r"channel\s*\d+",
        r"\b\d{1,2}:\d{2}:\d{2}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"surveillance",
        r"security camera"
    ]

    for p in patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", text).strip()


# -------------------------- PARSER -------------------------------------------
def parse_vlm_output(text: str):
    text = text.strip()

    desc = ""
    label = "unknown"

    if "Description:" in text and "Label:" in text:
        parts = text.split("Label:")
        desc = parts[0].replace("Description:", "").strip()
        label = parts[1].strip().split()[0].lower()
    else:
        desc = text

    if label not in VALID_LABELS:
        label = "normal"

    return clean_text(desc), label


# -------------------------- KAFKA --------------------------------------------
def publish_event(frame, label, desc, score, cam_id):
    if not kafka_enabled:
        return

    try:
        _, buffer = cv2.imencode(".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        img_b64 = base64.b64encode(buffer).decode()

        event = {
            "camera_id": cam_id,
            "label": label,
            "description": desc,
            "score": float(score),
            "image": img_b64,
        }

        _kafka_producer.produce(
            KAFKA_TOPIC,
            key="anomaly",
            value=json.dumps(event).encode()
        )
        _kafka_producer.poll(0)

    except Exception as e:
        print(f"[Kafka error] {e}")


# -------------------------- VIDEO MODEL --------------------------------------
def run_videomae(frames):
    inputs = s1_processor(images=frames, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        out = s1_model(**inputs)
    return torch.softmax(out.logits, dim=-1)[0]


def best_frame(frames):
    scores = [
        cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
        for f in frames
    ]
    return frames[int(np.argmax(scores))]


# -------------------------- TASK ---------------------------------------------
@celery_app.task(name="run_anomaly_detection")
def run_anomaly_detection(rtsp_url: str, camera_id: str, task_id: str):

    load_models()
    from PIL import Image

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print("[ERROR] Stream not opened")
        return

    frame_buffer = deque(maxlen=VIDEO_WINDOW)
    vlm_buffer = deque(maxlen=VIDEO_WINDOW)

    frame_count = 0
    last_vlm_time = 0

    print(f"[START] Camera {camera_id}")

    try:
        while True:

            if redis_client.get(f"stop_anomaly:{task_id}"):
                print("[STOP] Signal received")
                break

            ret, frame = cap.read()
            if not ret:
                time.sleep(2)
                continue

            frame_count += 1

            small = cv2.cvtColor(cv2.resize(frame, FRAME_SIZE), cv2.COLOR_BGR2RGB)
            full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            frame_buffer.append(small)
            vlm_buffer.append(full)

            if frame_count % INFER_EVERY_N == 0 and len(frame_buffer) == VIDEO_WINDOW:

                probs = run_videomae(list(frame_buffer))
                score = probs[STAGE1_ANOMALY_IDX].item()

                print(f"[Score] {score:.3f}")

                if score > STAGE1_THRESHOLD:

                    if time.time() - last_vlm_time > STAGE3_COOLDOWN:

                        snap = best_frame(list(vlm_buffer))
                        pil_img = Image.fromarray(snap)

                        prompt = """
Describe visible human activity in detail.
Then classify with one label:
[normal], [violence], [theft], [trespassing], [vandalism], [unusual_behavior]

Format:
Description: ...
Label: ...
Ignore camera text and overlays.
"""

                        messages = [{
                            "role": "user",
                            "content": [
                                {"type": "image"},
                                {"type": "text", "text": prompt}
                            ]
                        }]

                        text_input = s3_processor.apply_chat_template(
                            messages,
                            add_generation_prompt=True
                        )

                        inputs = s3_processor(
                            images=[pil_img],
                            text=text_input,
                            return_tensors="pt"
                        ).to(DEVICE)

                        with torch.no_grad():
                            out = s3_model.generate(
                                **inputs,
                                max_new_tokens=STAGE3_MAX_TOKENS,
                                do_sample=False,
                                temperature=0.0
                            )

                        raw = s3_processor.decode(
                            out[0][inputs["input_ids"].shape[1]:],
                            skip_special_tokens=True
                        ).strip()

                        desc, label = parse_vlm_output(raw)

                        print(f"[SCENE] {desc} | {label}")

                        publish_event(
                            snap,
                            label,
                            desc,
                            score,
                            camera_id
                        )

                        last_vlm_time = time.time()

            time.sleep(0.01)

    finally:
        cap.release()
        print("[DONE]")