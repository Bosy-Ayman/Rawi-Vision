import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { cameraAPI } from '../api/camera';
import ToastNotification from '../components/modals/ToastNotification';
import './AllCameras.css';

const AllCameras = () => {
    const [cameras, setCameras] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isDiscovering, setIsDiscovering] = useState(false);
    const [notification, setNotification] = useState(null);
    
    const navigate = useNavigate();

    const fetchCameras = async () => {
        try {
            const data = await cameraAPI.getAllCameras();
            setCameras(data);
            setIsLoading(false);
        } catch (err) {
            console.error("Failed to fetch cameras:", err);
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchCameras();
    }, []);

    const handleDiscover = async () => {
        setIsDiscovering(true);
        try {
            await cameraAPI.discoverCameras();
            setNotification({ type: 'success', title: 'Discovery Complete', message: 'Online cameras and RTSP streams synced successfully.' });
            setTimeout(() => setNotification(null), 5000);
        } catch (err) {
            console.error("Discovery error:", err);
            setNotification({ type: 'error', title: 'Discovery Failed', message: 'Could not connect to the discovery service.' });
            setTimeout(() => setNotification(null), 5000);
        } finally {
            setIsDiscovering(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Are you sure you want to delete this camera?")) return;
        
        setIsDeleting(true); 
        try {
            await cameraAPI.deleteCamera(id);
            setCameras(cameras.filter(cam => cam.id !== id));
        } catch (err) {
            console.error("Failed to delete camera:", err);
            alert('Error connecting to server to delete camera'); 
        } finally {
            setIsDeleting(false);
        }
    };

    const filteredCameras = cameras.filter(cam =>
        cam.room.toLowerCase().includes(searchTerm.toLowerCase()) ||
        cam.building.toLowerCase().includes(searchTerm.toLowerCase()) ||
        cam.mac_address.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <DashboardLayout title="Camera Directory">
            {notification && (
                <ToastNotification 
                    type={notification.type}
                    title={notification.title}
                    message={notification.message}
                    onClose={() => setNotification(null)}
                />
            )}
            <div className="all-cameras-container">
                <div className="page-header">
                    <h2 className="header-title">All Cameras</h2>
                    <div className="header-center">
                        <div className="search-bar">
                            <input
                                type="text"
                                placeholder="Search by room, building, or MAC..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>
                    <div className="header-right">
                        <button 
                            className="btn-add-new" 
                            onClick={handleDiscover}
                            disabled={isDiscovering}
                            style={{ marginRight: '10px', backgroundColor: '#3498db' }}
                        >
                            {isDiscovering ? 'Discovering...' : 'Sync / Discover'}
                        </button>
                        <button className="btn-add-new" onClick={() => navigate('/dashboard/camera-onboarding')}>
                            + Add Camera
                        </button>
                    </div>
                </div>

                {isLoading ? (
                    <div className="loading">Loading cameras...</div>
                ) : (
                    <div className="camera-grid">
                        {filteredCameras.length > 0 ? (
                            filteredCameras.map((cam, index) => (
                                <div key={cam.id || index} className="camera-card">
                                    <div className="card-image">
                                        <div className="icon-placeholder">
                                            🎥
                                        </div>
                                    </div>
                                    <div className="card-info">
                                        <h3>{cam.room}</h3>
                                        <p className="location-badge">{cam.building}</p>
                                        <p className="mac-address">MAC: {cam.mac_address}</p>
                                    </div>
                                    
                                    <button 
                                        className="btn-delete-camera" 
                                        onClick={(e) => { e.stopPropagation(); handleDelete(cam.id); }}
                                        disabled={isDeleting}
                                    >
                                        Delete Camera
                                    </button>
                                </div>
                            ))
                        ) : (
                            <div className="empty-state">
                                <p>No cameras found matching your search.</p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default AllCameras;
