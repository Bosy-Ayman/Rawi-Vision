import React, { useEffect, useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { anomalyAPI } from '../api/anomalies';

const WS_URL = 'ws://127.0.0.1:8000/anomalies/ws/live';

function timeAgo(isoString) {
    const diff = Math.floor((Date.now() - new Date(isoString)) / 1000);
    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
}

const BADGE_COLORS = {
    violence: '#dc2626',
    theft: '#ea580c',
    vandalism: '#d97706',
    unusual_behavior: '#7c3aed',
    unknown: '#6b7280',
};

const Anomalies = () => {
    const [anomalies, setAnomalies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [notification, setNotification] = useState(null);

    // Load historical anomalies on mount using the existing apiClient
    useEffect(() => {
        anomalyAPI.getAnomalies()
            .then((data) => {
                setAnomalies(data);
                setLoading(false);
            })
            .catch((err) => {
                setError(err.detail || 'Failed to load anomalies.');
                setLoading(false);
            });
    }, []);

    // WebSocket: subscribe to live anomaly events
    // Token must be passed as query param (WebSockets can't use Auth headers)
    // WebSocket: subscribe to live anomaly events with auto-reconnect
    useEffect(() => {
        const token = localStorage.getItem('access_token');
        if (!token) return;

        let ws = null;
        let reconnectTimer = null;
        let isComponentMounted = true;

        const connectWebSocket = () => {
            if (!isComponentMounted) return;

            ws = new WebSocket(`${WS_URL}?token=${token}`);

            ws.onopen = () => {
                console.log('[WS] Connected to live anomaly stream');
            };

            ws.onmessage = (event) => {
                try {
                    const newAnomaly = JSON.parse(event.data);
                    if (newAnomaly.type === 'ping') return;

                    console.log('[WS] Received live anomaly:', newAnomaly);

                    let isDuplicate = false;
                    setAnomalies((prev) => {
                        // Avoid duplicates if reconnecting caused identical events
                        if (prev.some(a => a.id === newAnomaly.id)) {
                            isDuplicate = true;
                            return prev;
                        }
                        return [newAnomaly, ...prev];
                    });

                    if (!isDuplicate) {
                        console.log('[WS] Triggering notification UI for:', newAnomaly.id);
                        // Show notification
                        setNotification(newAnomaly);
                        setTimeout(() => {
                            if (isComponentMounted) setNotification(null);
                        }, 7000);
                    } else {
                        console.log('[WS] Ignored duplicate message ID:', newAnomaly.id);
                    }
                } catch (e) {
                    console.warn('[WS] Could not parse message:', event.data, e);
                }
            };

            ws.onerror = (err) => {
                console.error('[WS] Error:', err);
            };

            ws.onclose = () => {
                console.log('[WS] Disconnected. Attempting to reconnect in 3s...');
                if (isComponentMounted) {
                    reconnectTimer = setTimeout(connectWebSocket, 3000);
                }
            };
        };

        connectWebSocket();

        return () => {
            isComponentMounted = false;
            clearTimeout(reconnectTimer);
            if (ws) ws.close();
        };
    }, []);

    return (
        <DashboardLayout title="Anomalies">
            {/* Live Anomaly Notification Toast */}
            {notification && (
                <div style={{
                    position: 'fixed',
                    top: '20px',
                    right: '20px',
                    backgroundColor: '#fff1f2',
                    borderLeft: '4px solid #ef4444',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                    padding: '16px',
                    borderRadius: '8px',
                    zIndex: 9999,
                    width: '320px',
                    animation: 'slideIn 0.3s ease-out',
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong style={{ color: '#be123c', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '20px' }}>🚨</span> Anomaly Detected
                        </strong>
                        <button
                            onClick={() => setNotification(null)}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px', color: '#9ca3af' }}
                        >
                            ✕
                        </button>
                    </div>
                    <div style={{ marginTop: '12px' }}>
                        <p style={{ color: '#111827', fontWeight: '600', textTransform: 'uppercase', fontSize: '14px', margin: 0 }}>
                            {notification.anomaly_type}
                        </p>
                        <p style={{ color: '#4b5563', fontSize: '13px', margin: '4px 0 0 0' }}>
                            {notification.description || 'Unknown event detected.'}
                        </p>
                    </div>
                </div>
            )}
            <div className="anomalies-container">
                {loading && <p style={{ color: '#9ca3af' }}>Loading anomalies...</p>}
                {error && <p style={{ color: '#ef4444' }}>Error: {error}</p>}
                {!loading && !error && anomalies.length === 0 && (
                    <p style={{ color: '#9ca3af' }}>No anomalies detected yet.</p>
                )}
                <div className="anomalies-grid">
                    {anomalies.map((item) => (
                        <div key={item.id} className="anomaly-card">
                            <div className="anomaly-image-wrapper">
                                <img
                                    src={item.image_url || '/assets/images/camera.png'}
                                    alt={item.anomaly_type}
                                    className="anomaly-image"
                                    onError={(e) => { e.target.src = '/assets/images/camera.png'; }}
                                />
                            </div>
                            <div className="anomaly-content">
                                <span style={{
                                    backgroundColor: BADGE_COLORS[item.anomaly_type] || '#6b7280',
                                    color: 'white',
                                    padding: '2px 10px',
                                    borderRadius: '12px',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                    textTransform: 'uppercase',
                                }}>
                                    {item.anomaly_type}
                                </span>
                                <h3 className="anomaly-title" style={{ marginTop: '8px' }}>
                                    {item.description || 'No description available.'}
                                </h3>
                                <p className="anomaly-time" style={{ color: '#9ca3af', fontSize: '13px' }}>
                                    {item.detected_at ? timeAgo(item.detected_at) : ''}
                                    {' · '}
                                    Confidence: {item.confidence_score
                                        ? `${(item.confidence_score * 100).toFixed(1)}%`
                                        : 'N/A'}
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default Anomalies;
