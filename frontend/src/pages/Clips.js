import React, { useState, useEffect } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { searchAPI } from '../api/search';
import './Clips.css';

const Clips = () => {
    const [videos, setVideos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);

    useEffect(() => {
        fetchVideos();
    }, []);

    const fetchVideos = async () => {
        try {
            const data = await searchAPI.listVideos();
            setVideos(data.videos || []);
        } catch (err) {
            console.error("Failed to fetch videos", err);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (videoId) => {
        if (!window.confirm('Are you sure you want to delete this video?')) return;
        try {
            await searchAPI.deleteVideo(videoId);
            setVideos(videos.filter(v => v.video_id !== videoId));
        } catch (err) {
            console.error("Failed to delete video", err);
            alert("Failed to delete video");
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('camera_id', '00000000-0000-0000-0000-000000000000'); // Default test camera
        formData.append('sampling_rate', 16);

        setUploading(true);
        try {
            await searchAPI.uploadVideo(formData);
            fetchVideos(); // Refresh list to show pending video
        } catch (err) {
            console.error("Upload failed", err);
            alert("Upload failed. Ensure backend is running.");
        } finally {
            setUploading(false);
            e.target.value = null; // Reset input
        }
    };

    return (
        <DashboardLayout title="Video Clips Library">
            <div className="clips-container">
                <div className="clips-header">
                    <p>Manage recorded and uploaded video clips for AI indexing.</p>
                    <div className="upload-btn-wrapper">
                        <button className="upload-btn" disabled={uploading}>
                            {uploading ? 'Uploading...' : 'Upload Video (.mp4)'}
                        </button>
                        <input type="file" accept="video/mp4,video/x-m4v,video/*" onChange={handleUpload} />
                    </div>
                </div>
                
                {loading ? (
                    <p>Loading clips...</p>
                ) : (
                    <div className="insights-grid">
                        {videos.map((video) => (
                            <div key={video.video_id} className="insight-card">
                                <div className="insight-image-placeholder">
                                    <div className="video-status-overlay">
                                        <span className={`status-badge ${video.status}`}>
                                            {video.status.toUpperCase()}
                                        </span>
                                    </div>
                                </div>
                                <div className="insight-content" style={{ position: 'relative' }}>
                                    <h3 className="insight-title" style={{ fontSize: '0.9rem', marginBottom: '4px' }}>
                                        {video.filename}
                                    </h3>
                                    <p className="insight-description" style={{ fontSize: '0.8rem', color: '#666' }}>
                                        Uploaded: {new Date(video.date_created).toLocaleString()}
                                    </p>
                                    <button 
                                        className="delete-clip-btn" 
                                        onClick={() => handleDelete(video.video_id)}
                                        title="Delete Video"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>
                        ))}
                        {videos.length === 0 && <p>No videos found. Upload one or record from a camera.</p>}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default Clips;
