"""
Anomaly Detection Celery Task.

The actual heavy model loading (VideoMAE + SmolVLM) is done in a
completely separate subprocess (anomaly_worker.py) to avoid Windows
thread-pool / safetensors memory-mapping crashes inside Celery.

This file is intentionally kept import-light so that Celery's
autodiscover_tasks() does not crash on startup.
"""
import os
import sys
import time
import subprocess

from utils.celery_client import celery_app
from camera_ingestion.utils.redis import redis_client

WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "anomaly_worker.py")


@celery_app.task(name="run_anomaly_detection")
def run_anomaly_detection(rtsp_url: str, camera_mac: str, task_id: str):
    """
    Launch a fresh Python subprocess that loads the AI models and runs
    the detection loop. The Celery task simply monitors the stop key in
    Redis and terminates the subprocess when needed.
    """
    print(f"[Anomaly] Spawning worker subprocess for {camera_mac}...", flush=True)

    proc = subprocess.Popen(
        [sys.executable, WORKER_SCRIPT, rtsp_url, camera_mac, task_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,   # line-buffered so we see output in real time
    )

    print(f"[Anomaly] Worker subprocess started (PID {proc.pid})", flush=True)

    try:
        # Stream subprocess stdout/stderr to our Celery log in real time
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                print(f"[Anomaly Worker] {line}", flush=True)
            # Also check stop signal so we can kill the subprocess
            if redis_client.get(f"stop_anomaly:{task_id}"):
                print(f"[Anomaly] Stop signal received — terminating subprocess PID {proc.pid}", flush=True)
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
    except Exception as e:
        print(f"[Anomaly] Error monitoring subprocess: {e}", flush=True)
        proc.kill()
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print(f"[Anomaly] Task {task_id} finished.", flush=True)
