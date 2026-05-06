import cv2
import numpy as np
from ultralytics import YOLO

model = YOLO("yolov8m.pt")

def get_color_name(hsv_crop):
    # 1. Filter out low-saturation (gray/white) and low-value (black/dark) pixels
    # OpenCV ranges: S is 0-255, V is 0-255
    mask = (hsv_crop[:, :, 1] > 40) & (hsv_crop[:, :, 2] > 60)
    colorful_pixels = hsv_crop[mask]

    # 2. If mostly dark/gray pixels, determine if it's black or white
    # (If less than 10% of the crop is colorful, we assume the clothing is neutral)
    if len(colorful_pixels) < (hsv_crop.shape[0] * hsv_crop.shape[1] * 0.1):
        v_mean = np.mean(hsv_crop[:, :, 2])
        return "White/Gray" if v_mean > 120 else "Black/Dark"

    # 3. Find the most frequent Hue (0-179 in OpenCV) among the colorful pixels
    hues = colorful_pixels[:, 0]
    hist = np.bincount(hues, minlength=180)
    dominant_hue = np.argmax(hist)

    # 4. Map the dominant hue to a color
    if dominant_hue < 10 or dominant_hue > 160:
        return "Red"
    elif 10 <= dominant_hue < 25:
        return "Yellow/Orange"
    elif 25 <= dominant_hue < 85:
        return "Green"
    elif 85 <= dominant_hue < 130:
        return "Blue"
    elif 130 <= dominant_hue <= 160:
        return "Purple/Pink"
    else:
        return "Unknown"

cap = cv2.VideoCapture("videos/shoplifting2.mp4")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Added verbose=False to keep the terminal clean
    results = model(frame, conf=0.3, verbose=False)[0]

    for box in results.boxes:
        cls = int(box.cls[0])

        if cls == 0:  # PERSON only
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            w = x2 - x1
            h = y2 - y1

            # 🔥 Focus on the UPPER BODY (shirt) to avoid mixing pants/skin colors
            x1i = x1 + int(0.25 * w)
            x2i = x2 - int(0.25 * w)
            y1i = y1 + int(0.15 * h) # Start slightly below the head
            y2i = y1 + int(0.50 * h) # End around the waist

            # Safety check to ensure valid crop coordinates
            if x1i >= x2i or y1i >= y2i:
                continue

            crop = frame[y1i:y2i, x1i:x2i]

            if crop.size == 0:
                continue

            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            color_name = get_color_name(hsv)

            label = f"Person | {color_name}"

            # Draw outer bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Optional: Draw the inner crop box in blue so you can visualize where it's looking
            cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), (255, 0, 0), 1) 
            
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Better Color Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()