import cv2
from mtcnn import MTCNN
from keras_facenet import FaceNet
from ultralytics import YOLO
from embedding_manager import EmbeddingManager
from ultralytics import YOLO
import torchreid

THRESHOLD = 0.6  
REID_WEIGHTS = "osnet_x1_0_msmt17.pt" 

#------------------  Models -----------------------------
detector = MTCNN()
embedder = FaceNet()
yolo_model = YOLO('yolov8n.pt')

datamanager = torchreid.data.ImageDataManager(
    root="reid-data",
    sources="market1501",
    targets="market1501",
    height=256,
    width=128,
    batch_size_train=32,
    batch_size_test=100,
    transforms=["random_flip", "random_crop"]
)

model = torchreid.models.build_model(
    name="resnet50",
    num_classes=datamanager.num_train_pids,
    loss="softmax",
    pretrained=True
)

model = model.cuda()

optimizer = torchreid.optim.build_optimizer(
    model,
    optim="adam",
    lr=0.0003
)

scheduler = torchreid.optim.build_lr_scheduler(
    optimizer,
    lr_scheduler="single_step",
    stepsize=20
)

model = torchreid.models.build_model(
    name="resnet50",
    num_classes=datamanager.num_train_pids,
    loss="softmax",
    pretrained=True
)

model = model.cuda()

optimizer = torchreid.optim.build_optimizer(
    model,
    optim="adam",
    lr=0.0003
)

scheduler = torchreid.optim.build_lr_scheduler(
    optimizer,
    lr_scheduler="single_step",
    stepsize=20
)
engine = torchreid.engine.ImageSoftmaxEngine(
    datamanager,
    model,
    optimizer=optimizer,
    scheduler=scheduler,
    label_smooth=True
)

# ---------------------- Load Embeddings -----------------------
manager = EmbeddingManager(db_folder="embeddings_db")
manager.load_db_into_memory()

# ---------------------- Start camera --------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) 

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Mirror and Convert
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = frame.shape
    
    #------------------------------ PIPELINE ------------------------- 
    # [1] Detect Faces (MTCNN)
    # Returns a list of dicts: [{'box': [x, y, w, h],'confidence': 0.99}]
    results = detector.detect_faces(rgb_frame)
    print(results)
    for result in results:
        x, y, w_box,h_box = result['box']
        confidence = result['confidence']
            
        # Filter weak detections
        if confidence < 0.90:
            continue

        # top left -> (x, y) 
        x = max(0, x)
        y = max(0, y)
        # bottom right ->(x2, y2) 
        x2 = min(w, x + w_box)
        y2 = min(h, y+ h_box)

        # Crop Face
        face_crop =rgb_frame[y:y2, x:x2]
        if face_crop.size == 0: 
            continue

        # [2] Extract embedding (FaceNet)
        embeddings=embedder.embeddings([face_crop])
                
        if len(embeddings) > 0:
            embedding = embeddings[0]
            print('the embedding Length: ',len(embedding))
            # [3] FAISS search
            name, distance = manager.search_face(embedding)

            #[4] Visualization
            if distance < THRESHOLD and name !="Unknown":
                color = (0, 255,0) # green
                label_text = f"{name} ({distance:.2f})"
            else:
                color = (0, 0, 255) # red
                label_text = f"Unknown ({distance:.2f})"

            cv2.rectangle(frame, (x, y), (x2, y2), color, 2)
            cv2.putText(frame, label_text, (x, y- 10),cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
           
   
    if cv2.waitKey(1) & 0xFF == ord('q'): 
        break

cap.release()
cv2.destroyAllWindows()

