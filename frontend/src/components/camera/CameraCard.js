import React, { useEffect, useRef, useState, useCallback } from 'react';
import { BASE_URL } from '../../api/client';

const WS_BASE = BASE_URL.replace(/^http/, 'ws') + '/stream';
const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1000;   // doubles on each attempt (exponential backoff)

const CameraCard = ({ camera }) => {
    const canvasRef   = useRef(null);
    const wsRef       = useRef(null);
    const reconnectTimerRef    = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const isMountedRef         = useRef(true);

    // Keep a ref in sync with the pause state so the onmessage closure
    // always reads the current value (avoids stale-closure bug).
    const isPausedRef = useRef(false);

    // Track whether a frame is currently being decoded to avoid piling up
    // concurrent createImageBitmap calls on a slow client.
    const decodingRef = useRef(false);

    const [isConnected, setIsConnected]   = useState(false);
    const [isError, setIsError]           = useState(false);
    const [isPaused, setIsPaused]         = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);

    const cardRef = useRef(null);

    // ------------------------------------------------------------------
    // Frame rendering — fastest path using createImageBitmap.
    // Compared to new Image() + URL.createObjectURL + onload, this:
    //   • skips URL allocation/revocation
    //   • decodes the JPEG off the main thread (in browsers that support it)
    //   • gives a ready-to-draw ImageBitmap with no onload callback lag
    // ------------------------------------------------------------------
    const drawFrame = useCallback(async (data) => {
        if (isPausedRef.current || decodingRef.current) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        decodingRef.current = true;
        try {
            const blob   = data instanceof Blob ? data : new Blob([data], { type: 'image/jpeg' });
            const bitmap = await createImageBitmap(blob);

            if (!isMountedRef.current || isPausedRef.current) {
                bitmap.close();
                return;
            }

            // Resize canvas only when dimensions change (avoids layout thrash)
            if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
                canvas.width  = bitmap.width;
                canvas.height = bitmap.height;
            }

            const ctx = canvas.getContext('2d', { alpha: false });  // alpha:false = faster composite
            ctx.drawImage(bitmap, 0, 0);
            bitmap.close();   // Free GPU memory immediately
        } catch {
            // Malformed frame — silently skip
        } finally {
            decodingRef.current = false;
        }
    }, []);

    // ------------------------------------------------------------------
    // WebSocket connection
    // ------------------------------------------------------------------
    const connectWebSocket = useCallback(() => {
        if (!isMountedRef.current) return;
        if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
            setIsError(true);
            return;
        }

        const token = localStorage.getItem('access_token');
        if (!token) {
            setIsError(true);
            return;
        }

        const ws = new WebSocket(`${WS_BASE}/${camera.mac_address}?token=${token}`);
        wsRef.current = ws;

        // Receive binary data as Blob — required for createImageBitmap
        ws.binaryType = 'blob';

        ws.onopen = () => {
            if (!isMountedRef.current) return;
            reconnectAttemptsRef.current = 0;
            setIsConnected(true);
            setIsError(false);
        };

        ws.onmessage = (event) => {
            if (!isMountedRef.current) return;
            // drawFrame guards isPausedRef internally
            drawFrame(event.data);
        };

        ws.onerror = () => {
            if (!isMountedRef.current) return;
            setIsConnected(false);
            setIsError(true);
        };

        ws.onclose = () => {
            if (!isMountedRef.current) return;
            setIsConnected(false);

            const attempt = reconnectAttemptsRef.current;
            reconnectAttemptsRef.current = attempt + 1;

            // Exponential backoff: 1 s, 2 s, 4 s, 8 s, 16 s
            const delay = Math.min(BASE_RECONNECT_DELAY_MS * 2 ** attempt, 30_000);
            reconnectTimerRef.current = setTimeout(connectWebSocket, delay);
        };
    }, [camera.mac_address, drawFrame]);

    useEffect(() => {
        isMountedRef.current = true;
        connectWebSocket();

        const onFullscreenChange = () => {
            setIsFullscreen(!!document.fullscreenElement);
        };
        document.addEventListener('fullscreenchange', onFullscreenChange);

        return () => {
            isMountedRef.current = false;
            clearTimeout(reconnectTimerRef.current);
            wsRef.current?.close();
            document.removeEventListener('fullscreenchange', onFullscreenChange);
        };
    }, [connectWebSocket]);

    // ------------------------------------------------------------------
    // Controls
    // ------------------------------------------------------------------
    const handlePauseToggle = () => {
        setIsPaused(prev => {
            isPausedRef.current = !prev;
            return !prev;
        });
    };

    const handleFullscreen = () => {
        const el = cardRef.current;
        if (!el) return;
        if (!document.fullscreenElement) {
            el.requestFullscreen().catch(() => {});
        } else {
            document.exitFullscreen().catch(() => {});
        }
    };

    const handleManualReconnect = () => {
        reconnectAttemptsRef.current = 0;
        setIsError(false);
        clearTimeout(reconnectTimerRef.current);
        wsRef.current?.close();
        connectWebSocket();
    };

    // ------------------------------------------------------------------
    // Badge helpers
    // ------------------------------------------------------------------
    const isHardOffline = isError && reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS;

    const getBadgeClass = () => {
        if (isHardOffline)  return 'camera-badge--error';
        if (!isConnected)   return 'camera-badge--reconnecting';
        return 'camera-badge--live';
    };

    const getBadgeLabel = () => {
        if (isHardOffline)  return 'OFFLINE';
        if (!isConnected)   return 'CONNECTING…';
        return 'LIVE';
    };

    // ------------------------------------------------------------------
    // Render
    // ------------------------------------------------------------------
    return (
        <div className="camera-card" ref={cardRef}>
            <canvas ref={canvasRef} className="camera-canvas" />

            {isHardOffline && (
                <div className="camera-error-overlay">
                    <span className="camera-error-icon">⚠</span>
                    <p className="camera-error-text">Stream unavailable</p>
                    <button className="camera-retry-btn" onClick={handleManualReconnect}>
                        Reconnect
                    </button>
                </div>
            )}

            <div className={`camera-badge ${getBadgeClass()}`}>
                <span className="badge-dot" />
                <span className="badge-label">{getBadgeLabel()}</span>
            </div>

            <div className="camera-info-bar">
                <div className="camera-location">
                    <span className="camera-room">{camera.room || 'Room'}</span>
                    <span className="camera-building">{camera.building || 'Building'}</span>
                </div>
                <div className="camera-controls">
                    <button
                        className="camera-ctrl-btn"
                        onClick={handlePauseToggle}
                        title={isPaused ? 'Resume' : 'Pause'}
                    >
                        {isPaused ? '▶' : '❚❚'}
                    </button>
                    <button
                        className="camera-ctrl-btn"
                        onClick={handleFullscreen}
                        title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
                    >
                        ⛶
                    </button>
                </div>
            </div>
        </div>
    );
};

export default CameraCard;