# Anomaly Detection Pipeline Progress

## Approaches Tested

1. Pretrained Model (2-Stage): Stage 1 (Anomaly Detector) -> Stage 2 (14-class Crime Classifier). Result: Failed to generalize well. -- it was from a repository not huggingface

2. VLM + Pretrained Model: Used CLIP as VLM + Anomaly Detector. Result: Poor performance.

3. VLM Only : Direct crime classification using Video Transformers (e.g., VideoMAE).

  • Pros: Learns temporal patterns, understands motion, end-to-end training.

  • Cons: Heavy GPU requirements, slower for real time, hard to deploy on edge devices.

## Current Pipeline Status

• Stage 1 (Binary Detection): Using `Nikeytas/videomae-crime-detector-fixed-format`. Status: Works fine for detecting Normal vs. Anomaly.

• Stage 2 (Classification): Planning to test `OPear/videomae-large-finetuned-UCF-Crime` for 14-class categorization. -- alot of misclassification

• Stage 3 (Weapon Detection): I will search on kaggle

## Key Observations & Learnings

• Threshold Differences: There is a noticeable difference in detection thresholds between real-time webcam feeds and standard uploaded videos. This discrepancy needs to be organized and accounted for in the deployment logic.
