from ultralytics import YOLO
import cv2
import os
import glob


def load_model(path="yolov8s.pt"):
    print("Loading YOLO...")
    return YOLO(path)


def detect_and_filter(frames_dir, output_dir, model, conf=0.25, allowed=None):

    os.makedirs(output_dir, exist_ok=True)

    frames = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))
    print(f"Detecting on {len(frames)} frames")

    kept = 0

    for i, f in enumerate(frames):

        img = cv2.imread(f)
        if img is None:
            continue

        results = model(f, conf=conf)[0]

        valid = False

        for box in results.boxes:
            cls = int(box.cls)
            name = results.names[cls]

            if allowed and name not in allowed:
                continue

            valid = True

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, name, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        #  keep ONLY frames with objects
        if valid:
            out_path = os.path.join(output_dir, os.path.basename(f))
            cv2.imwrite(out_path, img)
            kept += 1

        if i % 50 == 0:
            print(f"processed {i}")

    print(f"Kept {kept} frames after object filtering")