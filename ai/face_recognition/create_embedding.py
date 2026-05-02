import cv2
import os
import pickle
import numpy as np
import torch
from ultralytics import YOLO
from keras_facenet import FaceNet

# ---------------------- DEVICE ----------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

# ---------------------- MODELS ----------------------
yolo_face = YOLO("yolov12m-face.pt").to(device)
embedder = FaceNet()

# ---------------------- CREATE EMBEDDING ----------------------
def create_embedding(person_name, image_folders, embeddings_folder="embeddings_db"):
    embeddings = []
    processed = 0
    errors = []

    print(f"\n[INFO] Processing: {person_name}")

    for folder in image_folders:
        if not os.path.isdir(folder):
            continue

        for filename in sorted(os.listdir(folder)):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            filepath = os.path.join(folder, filename)
            image = cv2.imread(filepath)

            if image is None:
                errors.append(f"Could not read {filepath}")
                continue

            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # ---------------- YOLO FACE DETECTION ----------------
            results = yolo_face(rgb_image, verbose=False, conf=0.5)

            boxes = results[0].boxes

            if boxes is None or len(boxes) == 0:
                errors.append(f"No face detected in {filepath}")
                continue

            boxes = boxes.xyxy.cpu().numpy()

            # choose largest face
            best_idx = 0
            max_area = 0

            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes[i]
                area = (x2 - x1) * (y2 - y1)

                if area > max_area:
                    max_area = area
                    best_idx = i

            x1, y1, x2, y2 = map(int, boxes[best_idx])

            # safety clipping
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(rgb_image.shape[1], x2)
            y2 = min(rgb_image.shape[0], y2)

            face_crop = rgb_image[y1:y2, x1:x2]

            if face_crop.size == 0:
                continue

            # resize for FaceNet
            face_crop = cv2.resize(face_crop, (160, 160))

            # ---------------- FACENET ----------------
            embedding = embedder.embeddings([face_crop])[0]

            embeddings.append(embedding)
            processed += 1

    print(f"[INFO] {person_name}: valid faces = {processed}")

    # ---------------- SAVE ----------------
    if len(embeddings) == 0:
        print(f"[WARNING] No embeddings generated for {person_name}")
        return 0, None, errors

    avg_embedding = np.mean(np.array(embeddings), axis=0)

    save_dir = os.path.join(embeddings_folder, person_name)
    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, f"{person_name}.pkl")

    with open(save_path, 'wb') as f:
        pickle.dump(avg_embedding, f)

    print(f"[SAVED] {save_path}")

    return processed, save_path, errors


# ---------------------- GENERATE ALL EMBEDDINGS ----------------------
def generate_embeddings(augmented="augmented", faces="faces", embeddings_folder="embeddings_db"):
    os.makedirs(embeddings_folder, exist_ok=True)

    people = set()

    # collect all people
    for source in [augmented, faces]:
        if os.path.isdir(source):
            for person in os.listdir(source):
                path = os.path.join(source, person)
                if os.path.isdir(path):
                    people.add(person)

    print("\nPeople found:", people)

    stats = {
        "processed_people": 0,
        "total_images": 0,
        "total_errors": 0
    }

    for person_name in sorted(people):
        image_folders = []

        for source in [augmented, faces]:
            path = os.path.join(source, person_name)
            if os.path.isdir(path):
                image_folders.append(path)

        count, pkl_path, errors = create_embedding(
            person_name,
            image_folders,
            embeddings_folder
        )

        print(f"\n--- {person_name} SUMMARY ---")
        print("Images processed:", count)
        print("Saved to:", pkl_path)
        print("Errors:", len(errors))

        stats["processed_people"] += 1
        stats["total_images"] += count
        stats["total_errors"] += len(errors)

    return stats


# ---------------------- MAIN ----------------------
if __name__ == "__main__":
    stats = generate_embeddings()

    print("\n===== FINAL SUMMARY =====")
    print(stats)