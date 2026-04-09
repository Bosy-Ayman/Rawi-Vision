import cv2
import torch
import numpy as np
import time
from collections import deque
from transformers import AutoModelForVideoClassification, AutoImageProcessor

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

#----------------------------------- For Realtime Cameras ----------------------------------------

# Stage 1: Binary anomaly detector (fast gate) --> [anomaly vs normal]
STAGE1_MODEL_ID = "Nikeytas/videomae-crime-detector-fixed-format" 
STAGE1_ANOMALY_IDX = 1
STAGE1_THRESHOLD = 0.5

# Stage 2 : 14 class UCFCrime classifier (only fires when Stage 1 triggers)
STAGE2_MODEL_ID = "OPear/videomae-large-finetuned-UCF-Crime"
STAGE2_THRESHOLD = 0.3   # min confidence to trust Stage 2 label

VIDEO_WINDOW = 16
FRAME_SIZE = (224, 224)

# UCF-Crime 14 classes
CLASS_MAPPING = {
    "Abuse": 0, "Arrest": 1, "Arson": 2, "Assault": 3,"Burglary": 4, "Explosion": 5, "Fighting": 6, "Normal Videos": 7,
    "Road Accidents": 8, "Robbery": 9, "Shooting": 10, "Shoplifting": 11, "Stealing": 12, "Vandalism": 13
}

ID2LABEL = {v: k for k, v in CLASS_MAPPING.items()}

# Color per class (BGR)
CLASS_COLORS = {
    "Abuse":          (0,   0,   220),
    "Arrest":         (0,   140, 255),
    "Arson":          (0,   69,  255),
    "Assault":        (0,   0,   255),
    "Burglary":       (0,   165, 255),
    "Explosion":      (0,   50,  255),
    "Fighting":       (36,  28,  237),
    "Normal Videos":  (0,   200, 0  ),
    "Road Accidents": (0,   215, 255),
    "Robbery":        (60,  20,  220),
    "Shooting":       (0,   0,   180),
    "Shoplifting":    (30,  105, 210),
    "Stealing":       (42,  42,  165),
    "Vandalism":      (19,  69,  139),
}

# ------------------------- MODEL LOADING -------------------------------
s1_processor = AutoImageProcessor.from_pretrained(STAGE1_MODEL_ID)
s1_model = AutoModelForVideoClassification.from_pretrained(STAGE1_MODEL_ID).to(DEVICE)
s1_model.eval()
s2_processor = AutoImageProcessor.from_pretrained(STAGE2_MODEL_ID)
s2_model = AutoModelForVideoClassification.from_pretrained(
    STAGE2_MODEL_ID,
    label2id=CLASS_MAPPING,
    id2label=ID2LABEL,
    ignore_mismatched_sizes=True
).to(DEVICE)
s2_model.eval()

#---------------------------- VIDEO SETUP ------------------------------
cap = cv2.VideoCapture(0)
frame_buffer = deque(maxlen=VIDEO_WINDOW)

s1_score    = 0.0
is_anomaly  = False
s2_label    = "—"
s2_score    = 0.0
fps_display = 0.0

print("Press 'q' to quit.")

# ====================== INFERENCE HELPER ======================
def run_inference(model, processor, frames):
    inputs = processor(images=frames, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        if DEVICE == 'cuda':
            with torch.autocast(device_type='cuda', dtype=torch.float16):
                outputs = model(**inputs)
        else:
            outputs = model(**inputs)
    return torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

#------------------------------------------------------------------
while True:
    loop_start = time.time()

    ret, frame = cap.read()
    if not ret:
        print("End of video.")
        break

    # Preprocess frame for model
    frame_rgb = cv2.cvtColor(cv2.resize(frame, FRAME_SIZE), cv2.COLOR_BGR2RGB)
    frame_buffer.append(frame_rgb)

    if len(frame_buffer) == VIDEO_WINDOW:
        frames = list(frame_buffer)

        #  Stage 1: Binary gate 
        s1_probs   = run_inference(s1_model, s1_processor, frames)
        s1_score   = s1_probs[STAGE1_ANOMALY_IDX].item()
        is_anomaly = s1_score > STAGE1_THRESHOLD

        # Stage 2: Fine-grained (only when anomaly confirmed) 
        if is_anomaly:
            s2_probs      = run_inference(s2_model, s2_processor, frames)
            s2_class_idx  = s2_probs.argmax().item()
            s2_score      = s2_probs[s2_class_idx].item()
            s2_label      = ID2LABEL.get(s2_class_idx, f"Class {s2_class_idx}") \
                            if s2_score >= STAGE2_THRESHOLD else "Uncertain"
        else:
            s2_label = "—"
            s2_score = 0.0

    fps_display = 1.0 / max(time.time() - loop_start, 1e-6)

    #-----------------------------------VISUALIZATION--------------------------------
    h, w = frame.shape[:2]

    # Resolve colors
    s1_color = (0, 0, 255) if is_anomaly else (0, 220, 0)
    s2_color = CLASS_COLORS.get(s2_label, (180, 180, 180))

    # Top bar background
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 110), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Stage 1 row
    s1_text = f"Stage 1 | {'ANOMALY' if is_anomaly else 'NORMAL'}  {s1_score:.3f}"
    cv2.putText(frame, s1_text, (18, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, s1_color, 2)

    # Stage 2 row
    s2_display = f"{s2_label}  {s2_score:.3f}" if s2_label not in ("—", "Uncertain") else s2_label
    s2_text = f"Stage 2 | {s2_display}"
    cv2.putText(frame, s2_text, (18, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, s2_color, 2)

    # FPS (top-right)
    cv2.putText(frame, f"FPS {fps_display:.1f}", (w - 130, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

    # Alert banner at bottom

    if is_anomaly and s2_label not in ("—", "Uncertain"):
        banner_color = CLASS_COLORS.get(s2_label, (0, 0, 200))
        cv2.rectangle(frame, (0, h - 60), (w, h), banner_color, -1)
        cv2.putText(frame, f"!!! {s2_label.upper()} DETECTED !!!",
                    (18, h - 18), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (255, 255, 255), 3)
    elif is_anomaly:
        cv2.rectangle(frame, (0, h - 60), (w, h), (0, 0, 180), -1)
        cv2.putText(frame, "!!! ANOMALY DETECTED !!!",
                    (18, h - 18), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (255, 255, 255), 3)

    cv2.imshow(" UCF-Crime Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Quit by user.")
        break


cap.release()
cv2.destroyAllWindows()
print("Stopped.")