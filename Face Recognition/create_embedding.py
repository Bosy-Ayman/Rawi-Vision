import cv2
import os
import pickle
import numpy as np
from mtcnn import MTCNN
from keras_facenet import FaceNet

# ---------------------- Models--------------------
detector = MTCNN()
embedder = FaceNet()


def create_embedding(person_name, image_folders, embeddings_folder="embeddings_db"):
    embeddings = []
    processed= 0
    errors=[]

    for folder in image_folders:
        if not os.path.isdir(folder):
            continue
        
        for filename in sorted(os.listdir(folder)):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            filepath = os.path.join(folder, filename)
            image = cv2.imread(filepath)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
            # [1] MTCNN
            faces= detector.detect_faces(rgb_image)
                
            x, y, w, h =faces[0]['box']
            x =max(0, x)
            y =max(0, y)
            x2 = min(rgb_image.shape[1], x + w)
            y2 = min(rgb_image.shape[0], y + h)
            face_crop=rgb_image[y:y2, x:x2]
                
            # [2] FaceNet
            embedding =embedder.embeddings([face_crop])[0]
            embeddings.append(embedding)
            processed += 1
                
           
    
    # avg of augmented images per person (el7eta di hatet8ayar)
    if embeddings:
        avg_embedding=np.mean(np.array(embeddings), axis=0)

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
    
        
    for person_name in sorted(people):
        image_folders=[]
        for source in [augmented, faces]:
            person_path= os.path.join(source, person_name)
            if os.path.isdir(person_path):
                image_folders.append(person_path)
        
        # Create embedding
        count, pkl_path, errors = create_embedding(person_name, image_folders, embeddings_folder)
        
        print(f"{person_name}")
        print(f"Images: {count}")
        print(f"saved: {pkl_path}")
        print()
    
    return stats


if __name__ == "__main__":
    stats = generate_embeddings()