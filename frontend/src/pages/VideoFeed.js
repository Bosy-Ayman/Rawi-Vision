import React, { useEffect, useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { cameraAPI } from '../api/cameras';
import CameraCard from '../components/camera/CameraCard';
import './VideoFeed.css';

const VideoFeedPage = () => {
    const [cameras, setCameras] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [hasAccess, setHasAccess] = useState(true);

    useEffect(() => {
        // Enforce role access control locally
        const role = localStorage.getItem('user_role');
        if (role !== 'Manager' && role !== 'HR') {
            setHasAccess(false);
            setLoading(false);
            return;
        }

        cameraAPI.getAllCameras()
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
                <div className="camera-grid">
                    {cameras.map((camera) => (
                        <CameraCard key={camera.ip_address} camera={camera} />
                    ))}
                </div>
            )}
        </DashboardLayout>
    );
};

export default VideoFeedPage;
