#!/usr/bin/env python3
"""Pre-load and cache the SentenceTransformer model to avoid long startup delays"""

import os
import sys

print("[INFO] Pre-loading SentenceTransformer model 'all-MiniLM-L6-v2'...")
print("[INFO] This may take a few minutes on first run as the model is downloaded...")

try:
    from sentence_transformers import SentenceTransformer
    import torcha
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Using device: {device}")
    
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device=device)
    
    # Test encoding
    test_query = "person running"
    embedding = model.encode(test_query, convert_to_numpy=True)
    
    print(f"✓ Model loaded successfully!")
    print(f"✓ Embedding dimension: {len(embedding)}")
    print(f"✓ Cache location: {torch.hub.get_dir() if hasattr(torch, 'hub') else 'default'}")
    print("\n[SUCCESS] Ready to use search functionality!")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    print(f"[WARN] Search may be slow on first query while model downloads")
    sys.exit(1)
