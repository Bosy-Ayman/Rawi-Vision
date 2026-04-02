import cv2
import os
import pickle
import numpy as np
from mtcnn import MTCNN
from torch import device
from ultralytics import YOLO
from keras_facenet import FaceNet

# ---------------------- Models--------------------
print("Using device:", device)
detector = YOLO("yolov12m-face.pt").to(device)
embedder = FaceNet()

def create_embedding(person_name, image_folders, embeddings_folder="embeddings_db"):
    embeddings = []
    processed = 0
    errors = []

    for folder in image_folders:
        if not os.path.isdir(folder):
            continue
        
        for filename in sorted(os.listdir(folder)):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            filepath = os.path.join(folder, filename)
            image = cv2.imread(filepath)
            
            # Handle cases where the image file is corrupted or unreadable
            if image is None:
                errors.append(f"Could not read {filepath}")
                continue
                
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
            # [1] MTCNN
            faces = detector(rgb_image, verbose=False, conf=0.6)
                
          
            if len(faces[0].boxes) == 0:
                errors.append(f"No face detected in {filepath}")
                continue
                
            x, y, w, h = faces[0]['box']
            x = max(0, x)
            y = max(0, y)
            x2 = min(rgb_image.shape[1], x + w)
            y2 = min(rgb_image.shape[0], y + h)
            face_crop = rgb_image[y:y2, x:x2]
                
            # [2] FaceNet
            embedding = embedder.embeddings([face_crop])[0]
            embeddings.append(embedding)
            processed += 1
                
    # avg of augmented images per person
    if embeddings:
        avg_embedding = np.mean(np.array(embeddings), axis=0)

        save_path = os.path.join(embeddings_folder, person_name, f"{person_name}.pkl")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'wb') as f:
            pickle.dump(avg_embedding, f)
        
        return processed, save_path, errors 
        
    return 0, None, errors


def generate_embeddings(augmented="augmented", faces="faces", embeddings_folder="embeddings_db"):
    os.makedirs(embeddings_folder, exist_ok=True)
    
    # Find all people
    people = set()
    for source in [augmented, faces]:
        if os.path.isdir(source):
            for person_dir in os.listdir(source):
                if os.path.isdir(os.path.join(source, person_dir)):
                    people.add(person_dir)
                    
    # BUG FIX: Initialize a stats dictionary to keep track of results
    stats = {"processed_people": 0, "total_images": 0, "total_errors": 0}
        
    for person_name in sorted(people):
        image_folders = []
        for source in [augmented, faces]:
            person_path = os.path.join(source, person_name)
            if os.path.isdir(person_path):
                image_folders.append(person_path)
        
        # Create embedding
        count, pkl_path, errors = create_embedding(person_name, image_folders, embeddings_folder)
        
        print(f"--- {person_name} ---")
        print(f"Images processed: {count}")
        print(f"Saved to: {pkl_path}")
        if errors:
            print(f"Errors encountered: {len(errors)}")
        print()
        
        # Update stats
        stats["processed_people"] += 1
        stats["total_images"] += count
        stats["total_errors"] += len(errors)
    
    return stats

if __name__ == "__main__":
    final_stats = generate_embeddings()
    print("Process Complete. Summary:")
    print(final_stats)