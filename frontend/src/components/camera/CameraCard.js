import React, { useEffect, useRef, useState } from 'react';
import { BASE_URL } from '../../api/client';

const WS_BASE = BASE_URL.replace(/^http/, 'ws') + '/stream';
const MAX_RECONNECT_ATTEMPTS = 5;

const CameraCard = ({ camera }) => {
    const canvasRef = useRef(null);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const isMountedRef = useRef(true);

    const [isConnected, setIsConnected] = useState(false);
    const [isError, setIsError] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const cardRef = useRef(null);

    const connectWebSocket = () => {
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

        const cameraIdentifier = camera.ip_address || camera.mac_address;
        const ws = new WebSocket(`${WS_BASE}/${cameraIdentifier}?token=${token}`);
        wsRef.current = ws;

        ws.onopen = () => {
            if (!isMountedRef.current) return;
            reconnectAttemptsRef.current = 0;
            setIsConnected(true);
            setIsError(false);
        };

        ws.onmessage = (event) => {
            if (!isMountedRef.current || isPaused) return;
            const canvas = canvasRef.current;
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const blob = event.data instanceof Blob ? event.data : new Blob([event.data]);
            const url = URL.createObjectURL(blob);
            const img = new Image();
            img.onload = () => {
                if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
                    canvas.width = img.naturalWidth;
                    canvas.height = img.naturalHeight;
                }
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                URL.revokeObjectURL(url);
            };
            img.onerror = () => URL.revokeObjectURL(url);
            img.src = url;
        };

        ws.onerror = () => {
            if (!isMountedRef.current) return;
            setIsConnected(false);
            setIsError(true);
        };

        ws.onclose = () => {
            if (!isMountedRef.current) return;
            setIsConnected(false);
            reconnectAttemptsRef.current += 1;
            reconnectTimerRef.current = setTimeout(connectWebSocket, 3000);
        };
    };

    useEffect(() => {
        isMountedRef.current = true;
        connectWebSocket();

        return () => {
            isMountedRef.current = false;
            clearTimeout(reconnectTimerRef.current);
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [camera.ip_address, camera.mac_address]);

    const handlePauseToggle = () => setIsPaused(prev => !prev);

    const handleFullscreen = () => {
        const el = cardRef.current;
        if (!el) return;
        if (!document.fullscreenElement) {
            el.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
        } else {
            document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
        }
    };

    const handleManualReconnect = () => {
        reconnectAttemptsRef.current = 0;
        setIsError(false);
        clearTimeout(reconnectTimerRef.current);
        if (wsRef.current) wsRef.current.close();
        connectWebSocket();
    };

    const getBadgeClass = () => {
        if (isError && reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) return 'camera-badge--error';
        if (!isConnected) return 'camera-badge--reconnecting';
        return 'camera-badge--live';
    };

    const getBadgeLabel = () => {
        if (isError && reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) return 'OFFLINE';
        if (!isConnected) return 'CONNECTING…';
        return 'LIVE';
    };

    return (
        <div className="camera-card" ref={cardRef}>
            <canvas ref={canvasRef} className="camera-canvas" />

            {isError && reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS && (
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
                        title="Fullscreen"
                    >
                        {isFullscreen ? '⛶' : '⛶'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default CameraCard;
