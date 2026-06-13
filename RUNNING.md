# 🚀 Rawi Vision — Startup Guide

Run these commands **in order** every time you restart your machine.

---

## Step 1 — Start Docker Desktop

Open Docker Desktop manually from the Start Menu and **wait until the whale icon in the taskbar stops animating** (≈ 30–60 seconds).

Then verify containers are running:

```powershell
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"; docker ps
```

You should see **redis**, **postgres**, **rabbitmq**, and **backend-minio1-1** listed as `Up`.

If any are missing, start them:

```powershell
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"; docker start redis postgres rabbitmq backend-minio1-1
```

---

## Step 2 — Start the Backend (FastAPI)

Open a **new terminal**, navigate to the backend folder, and run:

```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"
venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8002
```

✅ Ready when you see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8002
```

---

## Step 3 — Start the Celery Worker (Recording)

> ⚠️ **This is required for recording to work.** Without it, recordings will be queued but never executed.

Open a **new terminal** and run:

```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"
venv\Scripts\celery.exe -A search.celery_tasks.tasks.celery_app worker --loglevel=info -P threads --concurrency=4 -Q celery
```

✅ Ready when you see:
```
[INFO/MainProcess] celery@Bosy ready.
```

---

## Step 4 — Start the Celery Worker (Summarization)

> ⚠️ **This is required for video summarization to work.** Without it, summarization tasks will be queued but never run.

Open a **new terminal** and run:

```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"
venv\Scripts\celery.exe -A utils.celery_client.celery_app worker --loglevel=info -P threads --concurrency=2 -Q summarization
```

✅ Ready when you see:
```
[INFO/MainProcess] celery@Bosy ready.
```

---

## Step 5 — Start the Frontend (React)

Open a **new terminal** and run:

```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\frontend
npm start
```

✅ Ready when you see:
```
Compiled successfully!
You can now view the app in the browser: http://localhost:3000
```

---

## Step 6 — Open the App

Go to: **http://localhost:3000**

---

## Quick Summary (Copy-Paste)

> Run each block in a **separate terminal window**.

**Terminal 1 — Backend:**
```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"; venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8002
```

**Terminal 2 — Celery Worker (Recording):**
```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"; venv\Scripts\celery.exe -A search.celery_tasks.tasks.celery_app worker --loglevel=info -P threads --concurrency=4 -Q celery
```

**Terminal 3 — Celery Worker (Summarization):**
```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
$env:DOCKER_HOST="npipe:////./pipe/dockerDesktopLinuxEngine"; venv\Scripts\celery.exe -A utils.celery_client.celery_app worker --loglevel=info -P threads --concurrency=2 -Q summarization
```

**Terminal 4 — Frontend:**
```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\frontend
npm start
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Recording starts but shows 0 chunks forever | Celery worker (Terminal 2) is not running → start it |
| Summarization stays "Queued" forever | Celery summarization worker (Terminal 3) is not running → start it |
| Summarized video doesn't show / won't play | **Restart the backend** (Terminal 1) — FastAPI must reload to apply code changes |
| Backend crashes on startup | Docker containers not ready → check Step 1 |
| Frontend shows blank page or API errors | Backend not running → check Step 2 |
| `docker ps` gives connection error | Docker Desktop is not open or still loading → wait 30s and retry |
| Recording stops immediately when clicking | Clear stale Redis keys (see below) |

**Clear stale Redis keys (if recording gets stuck):**
```powershell
cd C:\Users\pouss\Documents\CSAI\Rawi-Vision\backend
venv\Scripts\python.exe -c "import redis; r=redis.Redis(host='localhost',port=16379,decode_responses=True); [r.delete(k) for k in r.keys('stop:record:*') + r.keys('recording:status:*')]; print('Cleared.')"
```
