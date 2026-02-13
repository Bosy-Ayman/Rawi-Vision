# step 1 : Data augmentation
Create a 512 D that is based on a different variation (angles of the faces) 

Then applying data augmentation such as 
1. Rotation / Flip
2. Occlusion
3. Gaussian Blur --> i will try to make it adaptable whether the person is wearing mask, glasses..etc (Not Done it)

then i save these variations in an augmented folder

---
# step 2 : Create an embedding vector
Faiss Faiss Problem --> embedding_manager.py
 
- I'm reading from folders and to sql DB
- Im storing in pkl file per each user but the correct step is to store it in sql DB as a 512 D then use FAISS

---
# Step 3: The initial Pipline without the body detection fusion
Yolo --> MTCNN--> FaceNet-->Faiss(compare the embedding in the embedding_db folder and the realtime one)--> Result (Name/Confidence level)

---
# Step 3: add the body detection (In Progress)

1. Yolo Model (eg. nano,small)
   **input:** image frames
   **Output:** Bounding boxex of detected person(x1,y1,x2,y2),class IDs, confidence score

2. OsNet Model 
   **input:** Cropped person image (from YOLO)
   **Output:** Person embedding vector representing the body appearance

3. StrongSort (Tracker)
    **input:** frames
    **Output:** track ID per detected person (maintain the same id across frames)

4. MTCNN (Done)
    **input:** Frames
    **Output:** cropped face

5. FaceNet (Done)
    **input:** Cropped face (from MTCNN)
    **Output:** 512 D embedding

6. FAISS (Done)
    **input:** Face embedding vector
    **Output:** Closest matching face in database and similarity score

7. Face + Person Fusion
