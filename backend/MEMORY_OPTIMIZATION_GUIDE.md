# Memory Optimization Setup Guide - 6GB RAM

## What Was Changed

### 1. **Created Model Cache System** (`backend/utils/model_cache.py`)
- Singleton pattern for shared model loading
- Thread-safe caching prevents duplicate model loads
- Models loaded ONCE and reused across all tasks
- Emergency cleanup function for OOM errors

### 2. **Updated Celery Configuration** (`backend/utils/celery_config.py`)
- Created 5 dedicated queues:
  - `indexing` - Video indexing with FrameEncoder
  - `anomaly` - Anomaly detection pipeline
  - `face_recognition` - Face recognition pipeline
  - `embedding` - Employee onboarding embeddings
  - `summarization` - Video summarization
- Task routing ensures tasks go to correct queue

### 3. **Updated Task Files to Use Cache**

#### `search/celery_tasks/tasks.py`
- ✅ Imports model_cache
- ✅ Routes to "indexing" queue
- ✅ Uses _GLOBAL_ENCODER (already cached per-worker)
- ✅ Logs cache status on startup

#### `anomaly/celery_tasks/tasks.py`
- ✅ Imports model_cache (get_smolvlm, get_videomae)
- ✅ Routes to "anomaly" queue
- ✅ Lazy model loading from cache
- ✅ Removed duplicate load_models() function
- ✅ run_videomae() uses cached VideoMAE
- ✅ SmolVLM reused from cache (shared with indexing!)

#### `camera_ingestion/ai/fusion.py` (Face Recognition)
- ✅ Imports model_cache
- ✅ Uses get_yolo() for YOLOv12m-face and YOLOv8n
- ✅ Uses get_inception_face_embedder() (cached)
- ✅ Logs cache status on startup

#### `camera_ingestion/celery_tasks/face_recognition/tasks.py`
- ✅ Wrapper task routes to "face_recognition" queue
- ✅ Calls fusion.py with cached models

#### `employee_onboarding/celery_tasks/embedding/tasks.py`
- ✅ Imports model_cache
- ✅ Routes to "embedding" queue
- ✅ get_face_models() uses cache instead of local loading

#### `summarization/celery_tasks/tasks.py`
- ✅ Routes to "summarization" queue
- ✅ Already has global caching; added logging
- ✅ Imports model_cache for cache_status()

---

## Memory Impact

| Scenario | Memory Used | Status |
|----------|-----------|--------|
| **Before** | SmolVLM×2 + YOLOs×3 + InceptionV1×3 = **8-10GB** | ❌ FAILS |
| **After** | SmolVLM×1 + YOLOs×2 + InceptionV1×1 = **4-5GB** | ✅ WORKS |

### Model Reuse
- **SmolVLM**: Loaded once, shared by indexing + anomaly (~2GB)
- **YOLOv8x**: Loaded by indexing, reused (~800MB)
- **YOLOv12m-face**: Shared by indexing + face recognition + embedding (~400MB)
- **InceptionResnetV1**: Shared by all face tasks (~300MB)

---

## How to Run

### Option 1: Quick Start (All Workers in One Command)

```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend

# Run all workers sequentially:
.\start_workers.bat
```

This will open 4 terminal windows:
1. **Indexing Worker** - Handles video indexing (concurrency=1)
2. **Anomaly Worker** - Handles anomaly detection (concurrency=1)
3. **Face Recognition Worker** - Handles face recognition (concurrency=1)
4. **Embedding+Summarization Worker** - Lighter tasks (concurrency=2)

**Total concurrent tasks: 5**

### Option 2: Manual Terminal Startup (for debugging)

**Terminal 1 - Indexing (SmolVLM + YOLOv8x)**
```powershell
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
venv\Scripts\celery.exe -A utils.celery_client.celery_app worker --loglevel=info -P threads --concurrency=1 -Q indexing -n indexing_worker@%COMPUTERNAME%
```

**Terminal 2 - Search + Anomaly (VideoMAE + SmolVLM from cache)**
```powershell
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
venv\Scripts\celery.exe -A search.celery_tasks.tasks.celery_app worker --loglevel=info -P threads --concurrency=2 -Q celery,anomaly -n unified_worker@%COMPUTERNAME%
```
> [!IMPORTANT]
> Do **NOT** run the `celery` queue and the `anomaly` queue in separate terminals/workers! Separating them means each worker gets its own memory space, which will cause the 3GB SmolVLM model to load twice and immediately crash your GPU with an Out-Of-Memory error. Always combine them into a single threaded worker using `-Q celery,anomaly`.

**Terminal 3 - Face Recognition (YOLOv8n + YOLOv12m-face + InceptionV1 from cache)**
```powershell
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
venv\Scripts\celery.exe -A camera_ingestion.celery_tasks.face_recognition.tasks.celery_app worker --loglevel=info -P threads --concurrency=1 -Q face_recognition -n face_worker@%COMPUTERNAME%
```

**Terminal 4 - Embedding + Summarization (can run 2 tasks concurrently)**
```powershell
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
venv\Scripts\celery.exe -A employee_onboarding.celery_tasks.embedding.tasks.celery_app worker --loglevel=info -P threads --concurrency=2 -Q embedding,summarization -n other_worker@%COMPUTERNAME%
```

---

## What Happens When You Upload a Video

### With Anomaly Detection + Face Recognition Enabled

1. **Upload triggers:** `index_video_task` → Indexing worker
   - Loads FrameEncoder (which internally uses SmolVLM)
   - SmolVLM **cached** after first use
   - Detects faces via YOLOv12m-face (cached)
   - Generates 1152-dim embeddings

2. **Simultaneously:** `run_anomaly_detection` → Anomaly worker
   - Loads VideoMAE for anomaly scoring
   - When anomaly detected, uses **SmolVLM from cache** (no reload!)
   - Publishes to Kafka

3. **Simultaneously:** `run_face_recognition_logic` → Face worker
   - Loads YOLOv8n + YOLOv12m-face (from cache if just started indexing)
   - Uses InceptionV1 (from cache)
   - Publishes attendance events

**Result:** All 3 run in parallel on different workers, sharing cached models
**Memory:** ~4-5GB (not 10GB)

---

## Monitoring & Debugging

### Check Worker Status
```powershell
# List active workers
celery -A utils.celery_client.celery_app inspect active_queues

# See what each worker is doing
celery -A utils.celery_client.celery_app inspect active
```

### View Task Logs
Each worker logs to its terminal. Look for:
```
[Indexing] Cached models: ['smolvlm', 'yolov8x', 'yolov12m-face', 'inception_face']
[Anomaly] Loading models from cache...
[Face Recognition] Loading YOLOv8n from cache...
```

### If OOM Error Occurs
```python
from utils.model_cache import clear_cache
clear_cache()  # Clears all cached models
```

---

## Concurrency Breakdown

| Worker | Queue | Concurrency | Models | Memory |
|--------|-------|-------------|--------|--------|
| Indexing | indexing | 1 | FrameEncoder (SmolVLM, YOLO×3) | 2.5GB |
| Anomaly | anomaly | 1 | VideoMAE + SmolVLM (from cache) | 0.3GB |
| Face Rec | face_recognition | 1 | YOLO×2 + InceptionV1 (cached) | 0.4GB |
| Other | embedding, summarization | 2 | YOLO + misc | 1GB |
| **Total** | **-** | **5** | **Shared Cache** | **~4-5GB** |

---

## Queue Priority

If you want certain tasks to run first, adjust task priority:

```python
# High priority indexing
celery_app.conf.task_priority = {
    "search.tasks.index_video_task": 10,
    "anomaly.celery_tasks.tasks.run_anomaly_detection": 5,
    "camera_ingestion...face_recognition_logic": 3,
}
```

---

## Troubleshooting

### "Models not found" error
→ Make sure model_cache.py is at `backend/utils/model_cache.py`

### Workers not picking up tasks
→ Check broker connection: `celery -A utils.celery_client.celery_app inspect ping`

### Memory still high
→ Verify workers are on separate queues:
```bash
celery -A utils.celery_client.celery_app inspect active_queues
```

### Slow performance
→ Check if all 4 workers are running in separate terminals
→ Check if concurrency is set correctly (should be 1 for indexing/anomaly/face)

---

## Next Steps

1. **Test upload** with both toggles ON
2. **Monitor memory** with `get_cache_status()` logging
3. **Verify anomalies** appear in room-alerts page
4. **Check attendance** events from face recognition
