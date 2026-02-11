# step 1 : Data augmentation
Create a 512 D that is based on a different variation (angles of the faces) 

Then applying data augmentation such as 
1. Rotation / Flip
2. Occlusion
3. Gaussian Blur --> i will try to make it adaptable whether the person is wearing mask, glasses..etc (Not Done it)

then i Save these variations in an augmented folder

---
# step 2 : Create an embedding vector
## Faiss Faiss Problem --> embedding_manager.py
 
- I'm reading from folders and to sql DB
- Im storing in pkl file per each user but the correct step is to store it in sql DB as a 512 D then use FAISS

Why you need it: FAISS is a search engine for vectors. When you see a new face on the camera, converting it to a vector and ask FAISS: "Which vector in this file is closest to the one I just saw?"

The Output: FAISS is purely mathematical. It will reply with an Integer ID (e.g., "Match found at Index #42"). It does not know who "Ahmed" or "Sarah" is; it only knows "Vector #42".
---
# Step 3: The initial Pipline without the body detection fusion
Yolo --> MTCNN--> FaceNet-->Faiss(compare the embedding in the embedding_db folder and the realtime one)--> Result (Name/Confidence level)