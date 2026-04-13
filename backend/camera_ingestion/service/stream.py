import cv2
import asyncio
import time
import os
from fastapi import WebSocket, status
from camera_onboarding.service.metadata import CameraMetadataService

# ---------------------------------------------------------------------------
# Low-latency FFmpeg flags:
#   fflags=nobuffer   — disable input buffering
#   flags=low_delay   — minimize internal delay
#   analyzeduration   — cut probe time from 5 000 000 µs → 100 000 µs (0.1 s)
#   probesize         — cut probe data from 5 MB → 32 KB
#   max_delay         — hard-cap muxer delay to 0
# ---------------------------------------------------------------------------
os.environ["OPENCV_LOG_LEVEL"] = "QUIET"
os.environ["OPENCV_FFMPEG_DEBUG"] = "0"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|"
    "fflags;nobuffer|"
    "flags;low_delay|"
    "analyzeduration;100000|"
    "probesize;32768|"
    "max_delay;0"
)

# ---------------------------------------------------------------------------
# Module-level per-camera lock — prevents concurrent captures (OOM fix)
# ---------------------------------------------------------------------------
_active_streams: dict[str, asyncio.Lock] = {}

TARGET_FPS               = 15
FRAME_INTERVAL           = 1.0 / TARGET_FPS
MAX_CONSECUTIVE_FAILURES = 30       # ~3 s of bad reads before giving up
SEND_TIMEOUT_SEC         = 0.05     # Drop frame if socket can't accept in 50 ms
QUEUE_MAXSIZE            = 1        # 1 frame buffer — freshness over smoothness


class StreamService:
    def __init__(self, camera_metadata_service: CameraMetadataService):
        self.camera_metadata_service = camera_metadata_service

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def stream(self, websocket: WebSocket, mac_address: str) -> None:
        await websocket.accept()

        if not mac_address or mac_address == "undefined":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        lock = _active_streams.setdefault(mac_address, asyncio.Lock())
        if lock.locked():
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        async with lock:
            await self._do_stream(websocket, mac_address)

    # ------------------------------------------------------------------
    # Core stream logic
    # ------------------------------------------------------------------
    async def _do_stream(self, websocket: WebSocket, mac_address: str) -> None:

        # ── 1. Resolve RTSP URL ────────────────────────────────────────
        camera_metadata = await self.camera_metadata_service.get_camera_metadata_by_mac_address(
            mac_address=mac_address
        )
        if not camera_metadata or not camera_metadata.rtsp_urls:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        url: str = camera_metadata.rtsp_urls[0]

        # ── 2. Open capture in a thread (blocking call) ────────────────
        def open_capture() -> cv2.VideoCapture:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap

        cap: cv2.VideoCapture = await asyncio.to_thread(open_capture)

        if not cap.isOpened():
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # ── 3. Frame queue (size 1 — always the freshest frame) ────────
        frame_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        loop = asyncio.get_running_loop()

        # ── 4. Blocking capture loop — runs entirely in one thread ─────
        def capture_loop() -> None:
            consecutive_failures = 0

            try:
                while cap.isOpened():
                    t0 = time.monotonic()

                    ret, frame = cap.read()

                    if not ret or frame is None:
                        consecutive_failures += 1
                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            break
                        time.sleep(0.1)
                        continue

                    consecutive_failures = 0

                    # Resize + encode.
                    # 854x480 cuts JPEG payload ~50% vs 1280x720 while staying
                    # watchable for CCTV. Raise to (1280, 720) if bandwidth allows.
                    frame = cv2.resize(frame, (854, 480))
                    ok, buf = cv2.imencode(
                        ".jpg", frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 60]
                    )
                    if not ok:
                        continue

                    # Evict stale frame if queue is full so client always gets
                    # the latest frame rather than a queued-up old one.
                    if frame_queue.full():
                        try:
                            frame_queue.get_nowait()
                        except Exception:
                            pass

                    try:
                        loop.call_soon_threadsafe(frame_queue.put_nowait, buf.tobytes())
                    except Exception:
                        break

                    # Throttle to TARGET_FPS
                    elapsed = time.monotonic() - t0
                    wait = FRAME_INTERVAL - elapsed
                    if wait > 0:
                        time.sleep(wait)

            finally:
                # Sentinel tells the async sender to exit
                try:
                    loop.call_soon_threadsafe(frame_queue.put_nowait, None)
                except Exception:
                    pass

        # ── 5. Run capture thread; drain queue in async loop ───────────
        executor_future = loop.run_in_executor(None, capture_loop)

        try:
            while True:
                try:
                    frame_bytes = await asyncio.wait_for(frame_queue.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    break   # No frames for 10 s — stream is dead

                if frame_bytes is None:
                    break   # Sentinel — capture_loop exited cleanly

                try:
                    await asyncio.wait_for(
                        websocket.send_bytes(frame_bytes),
                        timeout=SEND_TIMEOUT_SEC,
                    )
                except asyncio.TimeoutError:
                    continue    # Client too slow — drop frame, stay real-time
                except Exception:
                    break       # WebSocket gone

        finally:
            cap.release()
            executor_future.cancel()
            try:
                await websocket.close()
            except Exception:
                pass