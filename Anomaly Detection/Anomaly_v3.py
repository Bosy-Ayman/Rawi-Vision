import re
import cv2
import torch
import time
import threading
import queue
import numpy as np
from collections import deque
from transformers import (
    AutoModelForVideoClassification,
    AutoImageProcessor,
    AutoProcessor,
    AutoModelForVision2Seq,
    BitsAndBytesConfig,   #used for quantization to allow ai models to run on smaller gpus
)
from PIL import Image

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

#----------------------  Config -------------------------------------------

STAGE1_MODEL_ID = "Nikeytas/videomae-crime-detector-fixed-format"
STAGE1_ANOMALY_IDX = 1
STAGE1_THRESHOLD = 0.5

STAGE3_MODEL_ID = "HuggingFaceTB/SmolVLM-Instruct"
STAGE3_COOLDOWN = 5.0
STAGE3_MAX_TOKENS= 35
STAGE3_NUM_BEAMS= 1

STAGE4_MODEL_ID  = 0
# -------------------------- for testing ---------------------------------
VIDEO_SOURCE  = "videos/assault_video (small).mp4" 
VIDEO_WINDOW  = 16
FRAME_SIZE    = (224, 224)
INFER_EVERY_N = 8

# -------------------------- Model loading -------------------------------

print("Loading Stage 1 (anomaly detection)")
# to prepare the video frames so they match the format the model was trained on
s1_processor=AutoImageProcessor.from_pretrained(STAGE1_MODEL_ID)
s1_model = AutoModelForVideoClassification.from_pretrained(STAGE1_MODEL_ID).to(DEVICE).eval()

print("Loading stage 2 (SmolVLM)")
s3_processor = AutoProcessor.from_pretrained(STAGE3_MODEL_ID)

s3_model = AutoModelForVision2Seq.from_pretrained(
    STAGE3_MODEL_ID,
    quantization_config=BitsAndBytesConfig(
        load_in_4bit = True,        # compress model's weights 32-> 4 bit chunks
        bnb_4bit_use_double_quant=True, 
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    ),
    device_map="auto",
    torch_dtype=torch.float16,
    low_cpu_mem_usage=True,
    attn_implementation="sdpa",
).eval()

#---------------------------------- Shared state ---------------------------------------

""" 
 Camera Thread:   Grabs a frame ==> Puts it in infer_queue.
 Stage 1 Thread:  Pulls from infer_queue ==> Updates detection_result.
 Stage 2 Thread:  If is_anomaly is True ==> Pulls from vlm_queue ==> Updates vlm_result.
"""

detection_result= {"is_anomaly": False,"s1_score": 0.0, "anomaly_type": "unknown"}
detection_lock=threading.Lock() # help for conccurency (only stage 1 can access the frame at a time )

vlm_result = {"text": "", "timestamp": 0.0, "anomaly_type": "unknown"}
vlm_lock = threading.Lock()


infer_queue =queue.Queue(maxsize=1)
vlm_queue= queue.Queue(maxsize=1)
workers_live=True 


# ------------------------------------------------------------------------------------
def build_vlm_prompt() -> str:
    """
    Build VLM prompt that detects and classifies anomaly types.
    Returns: Prompt string for anomaly classification
    """
    return """You are a strict surveillance video analyst.

Task: Detect and classify the anomaly in this surveillance frame.

Anomaly types to classify:
- violence: physical confrontation, striking, weapon use
- theft: taking items, shoplifting, breaking into containers
- trespassing: unauthorized area entry, climbing barriers, restricted zones
- vandalism: damaging property, graffiti, destruction
- unusual_behavior: abnormal movements, loitering, suspicious positioning
- normal: routine activity (if no anomaly detected)

Rules (MUST follow):
- One short factual sentence only (max 20 words)
- Describe ONLY what is clearly visible: person's hands, body movement, objects
- Output format: [ANOMALY_TYPE] Brief description
- NEVER mention time, clock, numbers, lighting, weather, emotion, intention
- NEVER use: appears, seems, might, probably, looks like, trying to, could be

Examples:
[violence] Person raising fist toward another person's face.
[theft] Person reaching into open register drawer.
[trespassing] Person climbing over fence in restricted area.
[vandalism] Person spray painting storefront window.
[unusual_behavior] Person standing motionless in middle of walkway.
[normal] People walking and browsing merchandise.

Start now:"""


#  It provides the anomaly type from the vlm_text (description)
def extract_anomaly_type(vlm_text: str) -> str:
    match =re.search(r'\[(\w+)\]', vlm_text)
    if match:
        atype = match.group(1).lower()
        valid_types = ["violence", "theft", "trespassing", "vandalism", "unusual_behavior", "normal"]
        if atype in valid_types:
            return atype
    return "unknown"


# Helpers
def run_videomae(model, processor, frames):
    inputs = processor(images=frames, return_tensors="pt").to(DEVICE) # resize the frame
    with torch.no_grad(), torch.autocast(device_type=DEVICE, dtype=torch.float16, enabled=(DEVICE == "cuda")):
        outputs = model(**inputs)
    return torch.nn.functional.softmax(outputs.logits, dim=-1)[0]


# It finds the best frame in a sequence to analyze to fix the issue of blurring that would cause the vlm to hallucinate
def sharpest_frame(frames):
    scores = []   
    for f in frames:
        gray =cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
        laplacian_matrix= cv2.Laplacian(gray, cv2.CV_64F)
        score= laplacian_matrix.var()
        scores.append(score)
    best_index= np.argmax(scores)
    return frames[best_index]

# -------------------------------------------------------------------------
def inference_worker():
    last_vlm = 0
    while workers_live:
        try:
            small, full =infer_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            s1_probs = run_videomae(s1_model, s1_processor, small)
            s1_score = s1_probs[STAGE1_ANOMALY_IDX].item() 
            is_anomaly = s1_score > STAGE1_THRESHOLD  # Constaint

            print(f" anomaly={is_anomaly}  s1_score={s1_score:.3f}")

            if is_anomaly:
                now=time.time()
                
                # this prevents the system from sending 30 snapshots a second for the same event, which would crash your GPU memory
                if (now - last_vlm) > STAGE3_COOLDOWN and not vlm_queue.full():
                    snap=sharpest_frame(full) # to pick the least motion blur
                    h, w = snap.shape[:2]
                    snap = cv2.resize(snap, (320, int(320 * h / w)))
                    vlm_queue.put_nowait(snap)
                    last_vlm = now

            with detection_lock:
                detection_result.update(is_anomaly=is_anomaly, s1_score=s1_score)
        except Exception as e:
            print(f"Stage 1 ERROR {e}")


def vlm_worker():
    while workers_live:
        try:
            frame_rgb=vlm_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            t0 = time.time()
            print(f"[VLM START] shape {frame_rgb.shape}")

            pil_img = Image.fromarray(frame_rgb)
            prompt = build_vlm_prompt()

            messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
            text_input = s3_processor.apply_chat_template(messages, add_generation_prompt=True)

            inputs = s3_processor(images=[pil_img], text=text_input, return_tensors="pt")
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

            with torch.no_grad():
                out = s3_model.generate(
                    **inputs,
                    do_sample=False,
                    num_beams=STAGE3_NUM_BEAMS,
                    max_new_tokens=STAGE3_MAX_TOKENS,
                    repetition_penalty=1.1,
                    early_stopping=True,
                )

            raw = s3_processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

            raw = re.sub(r"\d{1,2}:\d{2}(?:\s?[AP]M)?", "", raw) # remove time
            raw = re.sub(r"(?i)\b(appears|seems|might|probably|looks like|trying to|could be|may be)\b", "", raw)
            raw = re.sub(r"\s+", " ", raw).strip()
            if raw and len(raw) > 5:
                raw = raw[0].upper() + raw[1:]

            # Extract anomaly type
            anomaly_type = extract_anomaly_type(raw)

            elapsed = time.time() - t0
            print(f"[VLM DONE in {elapsed:.1f}s] Type: {anomaly_type} | {raw}")

            with vlm_lock:
                vlm_result.update(text=raw, timestamp=time.time(), anomaly_type=anomaly_type)
            
            with detection_lock:
                detection_result["anomaly_type"] = anomaly_type

            if DEVICE == "cuda":
                torch.cuda.empty_cache()

        except Exception as e:
            print(f" VLM ERROR {e}")
            with vlm_lock:
                vlm_result["text"] = "VLM error"

# On screen display 
def wrap_text(text: str, max_chars: int =72) -> list:
    words, lines, line = text.split(), [], ""
    for w in words:
        if len(line) + len(w)+1 > max_chars:
            lines.append(line)
            line = w
        else:
            line=(line + " " + w).strip()
    if line:
        lines.append(line)
    return lines

# ---------------------------------- Visualization -------------------------------------

def draw_top_bar(frame, r: dict, fps: float):
    h, w = frame.shape[:2]
    ov = frame.copy()
    cv2.rectangle(ov, (0, 0), (w, 115), (20, 20, 20), -1)
    cv2.addWeighted(ov, 0.60, frame, 0.40, 0, frame)

    s1_col = (0, 0, 255) if r["is_anomaly"] else (0, 220, 0)
    anomaly_type_str = f" [{r['anomaly_type'].upper()}]" if r["is_anomaly"] and r["anomaly_type"] != "unknown" else ""
    cv2.putText(frame, f" {'ANOMALY' if r['is_anomaly'] else 'NORMAL'}  {r['s1_score']:.3f}{anomaly_type_str}",
                (18, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, s1_col, 2)

    fps_txt = f"FPS {fps:.1f}" if fps > 0 else "FPS --"
    cv2.putText(frame, fps_txt, (w - 140, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (200, 200, 200), 2)


def draw_vlm_box(frame, vlm_text: str):
    if not vlm_text:
        return
    h, w = frame.shape[:2]
    lines = wrap_text(f"[VLM]  {vlm_text}")
    box_h = len(lines) * 23 + 18
    box_y = 120
    ov = frame.copy()
    cv2.rectangle(ov, (10, box_y), (w - 10, box_y + box_h), (15, 15, 15), -1)
    cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame)
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (18, box_y + 18 + i * 23), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 220, 50), 1)

def draw_alert_banner(frame, r: dict):
    h, w = frame.shape[:2]
    if r["is_anomaly"]:
        banner_color = (0, 0, 200)  # Default red
        anomaly_type = r.get("anomaly_type", "unknown").upper()
        
        # Color code by anomaly type
        if anomaly_type == "VIOLENCE":
            banner_color = (0, 0, 255)  # Bright red
        elif anomaly_type == "THEFT":
            banner_color = (0, 165, 255)  # Orange
        elif anomaly_type == "TRESPASSING":
            banner_color = (255, 0, 0)  # Blue
        elif anomaly_type == "VANDALISM":
            banner_color = (0, 255, 255)  # Yellow
        elif anomaly_type == "UNUSUAL_BEHAVIOR":
            banner_color = (255, 255, 0)  # Cyan
        
        cv2.rectangle(frame, (0, h - 62), (w, h), banner_color, -1)
        cv2.putText(frame, f"{anomaly_type} DETECTED ",
                    (18, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)

#-----------------------------------------------------------------------------

t_infer = threading.Thread(target=inference_worker, daemon=True)
t_vlm = threading.Thread(target=vlm_worker, daemon=True)
t_infer.start()
t_vlm.start()

cap = cv2.VideoCapture('videos/118956-716230948_small.mp4')
if not cap.isOpened():
    raise RuntimeError(f"Could not open video: {VIDEO_SOURCE}")

video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
frame_delay_ms = max(1, int(1000 / video_fps))
print(f"Video: {video_fps:.1f} FPS  →  target delay: {frame_delay_ms} ms")

frame_buffer = deque(maxlen=VIDEO_WINDOW)
vlm_frame_buffer = deque(maxlen=VIDEO_WINDOW)
frame_count = 0
fps_display = 0.0
last_frame = None

while True:
    loop_start = time.time()
    ret, frame = cap.read()

    if not ret:
     
        deadline = time.time() + 60.0
        while time.time() < deadline:
            with vlm_lock:
                vt = vlm_result["text"]
            if last_frame is not None:
                display = last_frame.copy()
                with detection_lock:
                    r = dict(detection_result)
                draw_top_bar(display, r, 0.0)
                draw_vlm_box(display, vt)
                draw_alert_banner(display, r)
                cv2.imshow("Anomaly Detection", display)
            if vt and not vt.startswith("Error") and len(vt) > 5:
                print(f"[VLM FINAL] {vt}")
                cv2.waitKey(5000)
                break
            if cv2.waitKey(200) & 0xFF == ord("q"):
                break
        break

    last_frame = frame.copy()
    frame_count += 1

    small_rgb = cv2.cvtColor(cv2.resize(frame, FRAME_SIZE), cv2.COLOR_BGR2RGB)
    full_rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_buffer.append(small_rgb)
    vlm_frame_buffer.append(full_rgb)

    if frame_count % INFER_EVERY_N == 0 and len(frame_buffer) == VIDEO_WINDOW:
        if not infer_queue.full():
            infer_queue.put_nowait((list(frame_buffer), list(vlm_frame_buffer)))

    with detection_lock:
        r = dict(detection_result)
    with vlm_lock:
        vlm_text = vlm_result["text"]

    draw_top_bar(frame, r, fps_display)
    draw_vlm_box(frame, vlm_text)
    draw_alert_banner(frame, r)

    cv2.imshow("Anomaly Detection", frame)

    elapsed_ms = int((time.time() - loop_start) * 1000)
    wait_ms = max(1, frame_delay_ms - elapsed_ms)
    fps_display = 1000.0 / max(elapsed_ms, 1)

    if cv2.waitKey(wait_ms) & 0xFF == ord("q"):
        print("Quit by user.")
        break


t_vlm.join(timeout=30.0)
workers_live = False
t_infer.join(timeout=5.0)
cap.release()
cv2.destroyAllWindows()
