"""
Singleton model cache - loads each model ONCE, reused across all tasks
Prevents SmolVLM, YOLOs, face models from loading multiple times
"""

import torch
import logging
from typing import Optional
from transformers import AutoProcessor, AutoModelForImageTextToText, AutoModelForImageClassification, BitsAndBytesConfig
from ultralytics import YOLO
import threading

logger = logging.getLogger(__name__)

# Thread-safe global cache
_model_lock = threading.Lock()
_model_cache = {}

def get_smolvlm():
    """Get cached Moondream model (600MB, lightweight)"""
    with _model_lock:
        if 'smolvlm' not in _model_cache:
            logger.info("Loading Moondream (lightweight)...")
            from transformers import AutoModelForCausalLM, AutoTokenizer

            model_id = "vikhyatk/moondream2"
            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                trust_remote_code=True,
                attn_implementation="eager",
                torch_dtype=torch.float16,
                device_map="cpu"
            )
            tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            _model_cache['smolvlm'] = (tokenizer, model)
            logger.info("Moondream loaded")
        return _model_cache['smolvlm']

def get_videomae():
    """Get cached VideoMAE anomaly detector (300MB)"""
    with _model_lock:
        if 'videomae' not in _model_cache:
            logger.info("Loading VideoMAE...")
            model = AutoModelForImageClassification.from_pretrained(
                "Nikeytas/videomae-crime-detector-fixed-format",
                device_map="auto" if torch.cuda.is_available() else "cpu"
            )
            _model_cache['videomae'] = model
            logger.info("VideoMAE loaded and cached")
        return _model_cache['videomae']

def get_yolo(model_name: str):
    """Get cached YOLO model (YOLOv8x, YOLOv8n, YOLOv12m-face, etc.)"""
    with _model_lock:
        if model_name not in _model_cache:
            logger.info(f"Loading {model_name}...")
            model = YOLO(model_name)
            if torch.cuda.is_available():
                model.to('cuda')
            _model_cache[model_name] = model
            logger.info(f"{model_name} loaded and cached")
        return _model_cache[model_name]

def get_inception_face_embedder():
    """Get cached InceptionResnetV1 (shared across all face tasks)"""
    with _model_lock:
        if 'inception_face' not in _model_cache:
            logger.info("Loading InceptionResnetV1...")
            from facenet_pytorch import InceptionResnetV1
            model = InceptionResnetV1(pretrained='vggface2')
            if torch.cuda.is_available():
                model.to('cuda')
            model.eval()
            _model_cache['inception_face'] = model
            logger.info("InceptionResnetV1 loaded and cached")
        return _model_cache['inception_face']

def clear_cache():
    """Emergency cleanup (call if OOM error)"""
    with _model_lock:
        logger.warning("Clearing model cache...")
        for key in _model_cache:
            try:
                model = _model_cache[key]
                if hasattr(model, 'to'):
                    model.to('cpu')
                del model
            except:
                pass
        _model_cache.clear()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        logger.info("Model cache cleared")

def get_cache_status():
    """Debug: see what's currently cached"""
    with _model_lock:
        models = list(_model_cache.keys())
        logger.info(f"Cached models: {models}")
        return models
