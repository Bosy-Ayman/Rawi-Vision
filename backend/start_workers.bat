@REM Optimal Celery setup for 6GB RAM laptop
@REM Runs 4 separate workers, each on its own queue
@REM Models are CACHED and SHARED across tasks in same queue

@echo off
cd /d C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
set DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine

@REM Worker 1: INDEXING (loads FrameEncoder once, reuses)
@REM - Uses SmolVLM, YOLOv8x, face detection
@REM - Concurrency=1 (heavy model, 6GB total)
echo Starting INDEXING worker...
start "Celery-Indexing" cmd /k venv\Scripts\celery.exe -A utils.celery_client.celery_app worker ^
  --loglevel=info -P threads --concurrency=1 -Q indexing -n indexing_worker@%%h

@REM Wait 5 seconds for first worker to start
timeout /t 5 /nobreak

@REM Worker 2: ANOMALY DETECTION (loads VideoMAE + SmolVLM from cache)
@REM - Reuses SmolVLM from cache (if indexing already loaded it)
@REM - Concurrency=1
echo Starting ANOMALY worker...
start "Celery-Anomaly" cmd /k venv\Scripts\celery.exe -A utils.celery_client.celery_app worker ^
  --loglevel=info -P threads --concurrency=1 -Q anomaly -n anomaly_worker@%%h

@REM Wait 3 seconds
timeout /t 3 /nobreak

@REM Worker 3: FACE RECOGNITION (isolated, doesn't share with indexing)
@REM - Separate worker so it doesn't block indexing/anomaly
@REM - Concurrency=1
echo Starting FACE RECOGNITION worker...
start "Celery-FaceRec" cmd /k venv\Scripts\celery.exe -A utils.celery_client.celery_app worker ^
  --loglevel=info -P threads --concurrency=1 -Q face_recognition -n face_worker@%%h

@REM Wait 3 seconds
timeout /t 3 /nobreak

@REM Worker 4: EMBEDDING + SUMMARIZATION (lighter tasks, can handle concurrency=2)
@REM - Combined queue for onboarding embeddings + video summaries
@REM - Concurrency=2
echo Starting EMBEDDING + SUMMARIZATION worker...
start "Celery-Other" cmd /k venv\Scripts\celery.exe -A utils.celery_client.celery_app worker ^
  --loglevel=info -P threads --concurrency=2 -Q embedding,summarization -n other_worker@%%h

echo.
echo ========================================
echo All Celery workers started!
echo ========================================
echo Indexing Worker:     concurrency=1 (SmolVLM + YOLOv8x)
echo Anomaly Worker:      concurrency=1 (VideoMAE + SmolVLM shared)
echo Face Rec Worker:     concurrency=1 (Face pipeline)
echo Other Worker:        concurrency=2 (Embedding + Summarization)
echo ========================================
echo Total max concurrent: 5 tasks
echo Memory impact: ~3-4GB (models cached after first load)
echo ========================================
echo.
pause
