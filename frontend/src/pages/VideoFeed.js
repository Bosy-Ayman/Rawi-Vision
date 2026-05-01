import React, { useEffect, useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { cameraAPI as ingestionAPI } from '../api/cameras';
import { cameraAPI as discoveryAPI } from '../api/camera';
import CameraCard from '../components/camera/CameraCard';
import ToastNotification from '../components/modals/ToastNotification';
import './VideoFeed.css';

const VideoFeedPage = () => {
    const [cameras, setCameras] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [hasAccess, setHasAccess] = useState(true);
    const [ingestionStatus, setIngestionStatus] = useState('Idle');
    const [isActionLoading, setIsActionLoading] = useState(false);
    const [isDiscovering, setIsDiscovering] = useState(false);
    const [notification, setNotification] = useState(null);

    useEffect(() => {
        // Enforce role access control locally
        const role = localStorage.getItem('user_role');
        if (role !== 'Manager' && role !== 'HR') {
            setHasAccess(false);
            setLoading(false);
            return;
        }

        ingestionAPI.getAllCameras()
            .then((data) => {
                setCameras(data || []);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Failed to load cameras", err);
                setError(err.detail || 'Failed to load cameras.');
                setLoading(false);
            });
    }, []);

    const handleStartIngestion = async () => {
        setIsActionLoading(true);
        try {
            // 1. First get the latest IPs via discovery (The "Sync" that works)
            const discoveredData = await discoveryAPI.discoverCameras();
            if (discoveredData && discoveredData.length > 0) {
                setCameras(discoveredData);
            }

            // 2. Now start the pipeline
            await ingestionAPI.startIngestion();
            setIngestionStatus('Running');
        } catch (err) {
            console.error("Start ingestion failed", err);
            alert("Failed to start ingestion");
        } finally {
            setIsActionLoading(false);
        }
    };

    const handleStopIngestion = async () => {
        setIsActionLoading(true);
        try {
            await ingestionAPI.stopIngestion();
            setIngestionStatus('Stopped');
        } catch (err) {
            console.error("Stop ingestion failed", err);
            alert("Failed to stop ingestion");
        } finally {
            setIsActionLoading(false);
        }
    };

    const handleDiscover = async () => {
        setIsDiscovering(true);
        try {
            const data = await discoveryAPI.discoverCameras();
            setCameras(data || []);

            setNotification({
                type: 'success',
                title: 'Discovery Complete',
                message: 'Online cameras and RTSP streams synced successfully.'
            });

            setTimeout(() => setNotification(null), 5000);
        } catch (err) {
            console.error("Discovery error:", err);
            setNotification({
                type: 'error',
                title: 'Discovery Failed',
                message: 'Could not connect to the discovery service.'
            });
            setTimeout(() => setNotification(null), 5000);
        } finally {
            setIsDiscovering(false);
        }
    };

    if (!hasAccess) {
        return (
            <DashboardLayout title="Video Feed">
                <div className="access-denied-screen">
                    <div className="access-denied-icon">🔒</div>
                    <h2>Access Denied</h2>
                    <p>You must be a Manager or HR representative to view live camera feeds.</p>
                </div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout title="Video Feed">
            {notification && (
                <ToastNotification
                    type={notification.type}
                    title={notification.title}
                    message={notification.message}
                    onClose={() => setNotification(null)}
                />
            )}
            {loading && (
                <div className="camera-loading-container">
                    <p>Loading cameras...</p>
                </div>
            )}

            {error && (
                <div className="camera-error-container">
                    <p>Error: {error}</p>
                </div>
            )}

            {!loading && !error && cameras.length === 0 && (
                <div className="camera-empty-container">
                    <p>No cameras registered yet. Please onboard cameras first.</p>
                </div>
            )}

            {!loading && !error && cameras.length > 0 && (
                <>
                    <div className="ingestion-control-bar" style={{ display: 'flex', gap: '10px', marginBottom: '20px', alignItems: 'center', backgroundColor: '#ffffff', padding: '15px', borderRadius: '8px', boxShadow: '0 4px 12px rgba(52, 152, 219, 0.1)', border: '1px solid #e1e8ed' }}>
                        <span style={{ color: '#2c3e50', marginRight: '10px', fontWeight: '500' }}>Global Ingestion Pipeline: <strong style={{ color: '#3498db' }}>{ingestionStatus}</strong></span>
                        <button
                            onClick={handleStartIngestion}
                            disabled={isActionLoading || ingestionStatus === 'Running'}
                            style={{ padding: '8px 16px', backgroundColor: '#2ecc71', color: 'white', border: 'none', borderRadius: '4px', cursor: (isActionLoading || ingestionStatus === 'Running') ? 'not-allowed' : 'pointer', opacity: (isActionLoading || ingestionStatus === 'Running') ? 0.6 : 1 }}
                        >
                            Start Pipeline
                        </button>
                        <button
                            onClick={handleStopIngestion}
                            disabled={isActionLoading || ingestionStatus === 'Stopped'}
                            style={{ padding: '8px 16px', backgroundColor: '#e74c3c', color: 'white', border: 'none', borderRadius: '4px', cursor: (isActionLoading || ingestionStatus === 'Stopped') ? 'not-allowed' : 'pointer', opacity: (isActionLoading || ingestionStatus === 'Stopped') ? 0.6 : 1 }}
                        >
                            Stop Pipeline
                        </button>

                        <div className="vertical-divider" style={{ width: '1px', height: '30px', backgroundColor: '#e1e8ed', margin: '0 10px' }}></div>

                        <button
                            onClick={handleDiscover}
                            disabled={isDiscovering}
                            style={{
                                padding: '8px 16px',
                                backgroundColor: '#3498db',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: isDiscovering ? 'not-allowed' : 'pointer',
                                opacity: isDiscovering ? 0.7 : 1
                            }}
                        >
                            {isDiscovering ? 'Discovering...' : 'Sync / Discover'}
                        </button>
                    </div>
                    <div className="camera-grid">
                        {cameras.map((camera) => (
                            <CameraCard key={camera.ip_address || camera.mac_address || camera.id} camera={camera} />
                        ))}
                    </div>
                </>
            )}
        </DashboardLayout>
    );
};

export default VideoFeedPage;
