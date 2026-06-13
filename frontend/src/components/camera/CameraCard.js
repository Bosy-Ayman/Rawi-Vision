import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BASE_URL } from '../../api/client';
import { searchAPI } from '../../api/search';

const WS_BASE = BASE_URL.replace(/^http/, 'ws') + '/stream';
const MAX_RECONNECT_ATTEMPTS = 5;

const CameraCard = ({ camera }) => {
    const navigate = useNavigate();
    const canvasRef = useRef(null);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const isMountedRef = useRef(true);

    const [isConnected, setIsConnected] = useState(false);
    const [isError, setIsError] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);
    
    // Recording state
    const [isRecording, setIsRecording] = useState(false);
    const [isStopping, setIsStopping] = useState(false);
    const [recordingChunks, setRecordingChunks] = useState(0);
    const [isActionLoading, setIsActionLoading] = useState(false);
    const [burnBboxes, setBurnBboxes] = useState(false);


    const cardRef = useRef(null);

    // Check initial recording status on mount
    useEffect(() => {
        const checkRecordingStatusOnMount = async () => {
            if (camera.id) {
                try {
                    const status = await searchAPI.getRecordingStatus(camera.id);
                    if (status.status === 'recording') {
                        setIsRecording(true);
                        setRecordingChunks(status.chunks_recorded || 0);
                    }
                } catch (err) {
                    console.error("Failed to fetch initial recording status on mount", err);
                }
            }
        };
        checkRecordingStatusOnMount();
    }, [camera.id]);

    // Poll recording status if recording
    useEffect(() => {
        let interval;
        if (isRecording && camera.id) {
            interval = setInterval(async () => {
                try {
                    const status = await searchAPI.getRecordingStatus(camera.id);
                    if (status.status === 'recording' || status.status === 'stopping') {
                        setRecordingChunks(status.chunks_recorded || 0);
                        setIsStopping(status.status === 'stopping');
                    } else if (status.status === 'not_found' || status.status === 'completed' || status.status === 'failed') {
                        setIsRecording(false);
                        setIsStopping(false);
                        clearInterval(interval);
                    }
                } catch (err) {
                    console.error("Failed to poll recording status", err);
                }
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [isRecording, camera.id]);

    const handleRecordToggle = async () => {
        if (!camera.id) {
            alert("No camera ID found.");
            return;
        }
        setIsActionLoading(true);
        try {
            if (isRecording) {
                await searchAPI.stopRecording(camera.id);
                // Don't flip isRecording immediately — let the poll confirm it stopped
                // (the task finishes the current chunk before actually stopping)
                setIsStopping(true);
            } else {
                await searchAPI.startRecording(camera.id, 600, 60, burnBboxes); // Record for 10 mins, chunk 60s
                setIsRecording(true);
                setIsStopping(false);
                setRecordingChunks(0);
            }
        } catch (err) {
            console.error("Recording action failed", err);
            alert(err.detail || "Failed to toggle recording.");
        } finally {
            setIsActionLoading(false);
        }
    };

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

            <div className={`camera-badge ${getBadgeClass()}`} style={{ display: 'flex', gap: '8px' }}>
                <span className="badge-dot" />
                <span className="badge-label">{getBadgeLabel()}</span>
            </div>
            
            {isRecording && (
                <div className="camera-badge camera-badge--recording" style={{ top: '10px', right: '10px', left: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span className="badge-dot" style={{ backgroundColor: isStopping ? '#f59e0b' : '#ffffff', width: '8px', height: '8px', borderRadius: '50%' }} />
                    <span className="badge-label" style={{ color: 'white', fontWeight: 'bold' }}>
                        {isStopping ? `STOPPING (${recordingChunks} ${recordingChunks === 1 ? 'chunk' : 'chunks'})` : `REC (${recordingChunks} ${recordingChunks === 1 ? 'chunk' : 'chunks'})`}
                    </span>
                </div>
            )}

            <div className="camera-info-bar">
                <div className="camera-location">
                    <span className="camera-room">{camera.room || 'Room'}</span>
                    <span className="camera-building">{camera.building || 'Building'}</span>
                </div>
                <div className="camera-controls" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {!isRecording && (
                        <label className="camera-bbox-label" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', cursor: 'pointer', color: burnBboxes ? '#3b82f6' : '#9ca3af', userSelect: 'none' }}>
                            <input
                                type="checkbox"
                                checked={burnBboxes}
                                onChange={(e) => setBurnBboxes(e.target.checked)}
                                disabled={isActionLoading}
                                style={{ cursor: 'pointer', width: '13px', height: '13px', margin: 0 }}
                            />
                            AI BBoxes
                        </label>
                    )}
                    <button
                        className="camera-ctrl-btn"
                        onClick={handleRecordToggle}
                        disabled={isActionLoading || isStopping}
                        title={isRecording ? (isStopping ? 'Stopping...' : 'Stop Recording AI') : 'Record & Index AI'}
                        style={{ color: isRecording ? (isStopping ? '#f59e0b' : '#ef4444') : 'inherit', fontWeight: 'bold' }}
                    >
                        {isRecording ? (isStopping ? '⏳ STOPPING' : '⏹ REC') : '⏺ AI REC'}
                    </button>

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
