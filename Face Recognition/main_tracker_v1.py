import cv2
from mtcnn import MTCNN
from keras_facenet import FaceNet
from embedding_manager import EmbeddingManager

THRESHOLD = 0.6  
#------------------  Models -----------------------------
detector = MTCNN()
embedder = FaceNet()

# ---------------------- Load Embeddings -----------------------
manager = EmbeddingManager(db_folder="embeddings_db")
manager.load_db_into_memory()

# ---------------------- Start camera --------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Camera not accessible")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to read frame")
        break

    # Mirror and Convert
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = frame.shape
    
    #------------------------------ PIPELINE ------------------------- 
    # [1] Detect Faces (MTCNN)
    results = detector.detect_faces(rgb_frame)
    
    for result in results:
        x, y, w_box,h_box = result['box']
        confidence = result['confidence']
            
        # Clamp coordinates
        x = max(0, x)
        y = max(0, y)
        x2 = min(w, x+ w_box)
        y2 = min(h, y + h_box)

        # Crop Face
        face_crop = rgb_frame[y:y2, x:x2]
        if face_crop.size == 0: 
            continue

        # [2] Extract embedding (FaceNet)
        embeddings = embedder.embeddings([face_crop])
        #print(embeddings.shape)
   
                
        if len(embeddings) > 0:
            embedding = embeddings[0]
            
            # [3] FAISS search
            name, distance = manager.search_face(embedding)

            # [4] Visualization
            if distance < THRESHOLD and name != "Unknown":
                color = (0, 255, 0)  # green
                label_text = f"{name} ({distance:.2f})"
            else:
                color = (0, 0, 255)  # red
                label_text = f"Unknown ({distance:.2f})"

            cv2.rectangle(frame, (x, y), (x2, y2), color, 2)
            cv2.putText(frame, label_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
   
    cv2.imshow("Face Recognition", frame)
   
    if cv2.waitKey(1) & 0xFF == ord('q'): 
        break

cap.release()
cv2.destroyAllWindows()