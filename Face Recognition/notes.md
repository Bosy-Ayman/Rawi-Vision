# Project Pipeline & Roadmap

## Step 1: Data Augmentation & Preprocessing

**Goal:** Generate a robust dataset to produce high-quality 512-dimensional embeddings, specifically focusing on facial angle variations and occlusions.

1. **Base Variation:**
    
    - Create dataset entries based on different facial angles/poses.
        
2. **Augmentation Techniques:**
    
    - **Rotation / Flip:** To handle camera tilt and mirroring.
        
    - **Occlusion:** Synthetic obstruction of facial features.
        
    - **Gaussian Blur:** Simulating out-of-focus frames or motion blur.
        
3. **Adaptive Masking (Todo):**
    
    - Implement logic to handle specific occlusions such as medical masks or glasses.
        
4. **Storage:**
    
    - Save all processed variations into the `augmented` directory.
        

## Step 2: Embedding Management

**Status:** Optimization in progress (`embedding_manager.py`)

- **Current Architecture:** Reading images from folders and storing embeddings in individual `.pkl` files per user.
    
- **Target Architecture (Refactoring):**
    
    1. Extract 512D vectors from images.
        
    2. Store metadata (User ID, Name) in an **SQL Database**.
        
    3. Store vectors in a **FAISS Index** for efficient similarity search.
        

## Step 3: Baseline Face Recognition Pipeline

**Status:** Functional **Description:** Initial implementation focusing solely on facial features, excluding body detection.

**Workflow:**  `MTCNN (Face Extraction)` $\rightarrow$ `FaceNet (Embedding)` $\rightarrow$ `FAISS (Similarity Search)` $\rightarrow$ `Result`

- **Comparison:** Real-time embeddings are compared against the `embedding_db` folder/index.
    
- **Output:** Recognized Name & Confidence Score.
    

## Step 4: Integrated Pipeline (Face + Body Fusion)

**Status:** In Progress **Description:** Fusing facial recognition with body re-identification to maintain identity across frames even when the face is not visible.

### 1. Person Detection (YOLO)

- **Model:** YOLO (Nano/Small)
    
- **Input:** Raw image frames
    
- **Output:** Bounding boxes $(x_1, y_1, x_2, y_2)$, Class IDs, Confidence Score
    

### 2. Body Feature Extraction (OsNet)

- **Model:** OsNet
    
- **Input:** Cropped person image (derived from YOLO bbox)
    
- **Output:** Person embedding vector representing body appearance
    

### 3. Object Tracking (StrongSORT)

- **Algorithm:** StrongSORT
    
- **Input:** Frames + Detections
    
- **Output:** Unique Track ID per person (maintains ID consistency across frames)
    

### 4. Face Detection (MTCNN) - _[Done]_

- **Input:** Raw Frames / Person Crops
    
- **Output:** Cropped face images
    

### 5. Face Embedding (FaceNet) - _[Done]_

- **Input:** Cropped face (from MTCNN)
    
- **Output:** 512D Embedding Vector
    

### 6. Similarity Search (FAISS) - _[Done]_

- **Input:** Face embedding vector
    
- **Output:** Closest matching identity from database + Similarity Score
    

### 7. Identity Fusion

- **Goal:** Combine **Face Identity** (High precision, intermittent availability) with **Body Track ID** (Continuous availability).
