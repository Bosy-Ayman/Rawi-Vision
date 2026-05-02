# Anomaly Detection Pipeline Progress

## Approaches Tested

- **Pretrained Model (2-Stage):** Implemented a pipeline from an external repository (non-Hugging Face) featuring an initial Anomaly Detector followed by a 14-class Crime Classifier.
    
    - _Result:_ Failed to generalize well across different environments.
        
- **VLM + Pretrained Model:** Paired CLIP (acting as the VLM) with a standard anomaly detector.
    
    - _Result:_ Poor overall performance and accuracy.
        
- **VLM Only (Current Focus):** Utilizing Video Transformers (e.g., VideoMAE) for direct crime classification.
    
    - _Pros:_ Effectively learns temporal patterns, understands motion, and supports end-to-end training.
        
    - _Cons:_ High GPU consumption and slower inference speeds for real-time applications.
        
    I didn't try it yet but i found a video that use it for Threft detection : https://www.youtube.com/watch?v=0o2RGqrmvtA

## Current Pipeline Status

- **Stage 1 (Binary Detection):** Implemented `Nikeytas/videomae-crime-detector-fixed-format`.
    
    - _Status:_ **Stable**. Works reliably for distinguishing between Normal and Anomaly states.
  
- **Stage 4 (VLM)**  to describe what happened 
   - _Status:_ **Done** SmolVLM .
        
## Key Observations & Active Optimizations

- **Environment-Specific Thresholds:** There is a noticeable difference in the optimal confidence thresholds between live webcam feeds and standard uploaded videos. This variance must be explicitly mapped and accounted for within the deployment logic to prevent false positives/negatives.
    
- **GPU Optimization via YOLO Trigger (In Progress):** To mitigate the heavy computational cost of the VideoMAE model, a YOLO-based person detection layer is being integrated. The exhaustive anomaly model will only be triggered when a person is detected in the frame, significantly reducing idle GPU load.

