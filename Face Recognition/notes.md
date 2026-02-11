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
