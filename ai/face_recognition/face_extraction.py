import cv2
from ultralytics import YOLO
import os
import torch


device = "cuda" if torch.cuda.is_available() else "cpu"
model = YOLO("yolov12m-face.pt")


video_path = "C:/Users/pouss/Documents/CSAI/Rawi-Vision/ai/face_recognition/video/test2.mp4"
cap = cv2.VideoCapture(video_path)


main_folder = "faces"
os.makedirs(main_folder, exist_ok=True)


# ==============================
frame_skip = 3
min_size = 40
MAX_IMAGES = 7
MAX_FRAMES = 90

frame_count = 0

# count images per person
count_per_person = {}

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1

    #  STOP after 50 frames
    if frame_count > MAX_FRAMES:
        break

    if frame_count % frame_skip != 0:
        continue


    results = model.track(frame, persist=True, verbose=False)

    for r in results:
        if r.boxes is None:
            continue

        boxes = r.boxes.xyxy
        ids = r.boxes.id

        if ids is None:
            continue

        for box, track_id in zip(boxes, ids):
            x1, y1, x2, y2 = map(int, box)
            track_id = int(track_id)

            # filter small faces
            if (x2 - x1) < min_size or (y2 - y1) < min_size:
                continue

            face = frame[y1:y2, x1:x2]

            if face.size == 0:
                continue


            person_folder = os.path.join(main_folder, f"person_{track_id}")
            os.makedirs(person_folder, exist_ok=True)

            # initialize counter
            if track_id not in count_per_person:
                count_per_person[track_id] = 0

            # limit to 7 images
            if count_per_person[track_id] >= MAX_IMAGES:
                continue

            filename = os.path.join(
                person_folder,
                f"frame_{frame_count}.jpg"
            )

            cv2.imwrite(filename, face)
            count_per_person[track_id] += 1


cap.release()
print("Done! Processed only first 50 frames.")