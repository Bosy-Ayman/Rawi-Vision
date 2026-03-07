import React from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';

const VideoFeedPage = () => {
    const feeds = [1, 2, 3, 4]; // 4 cameras

    return (
        <DashboardLayout title="Video Feed">
            <div className="video-grid">
                {feeds.map((id) => (
                    <div key={id} className="video-card">
                        <h3 className="video-title">Cafeteria camera</h3>
                        <div className="video-player-placeholder">
                            {/* Placeholder image acting as video feed */}
                            <img
                                src="/assets/images/camera.png"
                                alt="Feed"
                                style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.7 }}
                            />
                            <div className="video-controls-overlay">
                                <button className="play-btn">❚❚</button>
                                <div className="timeline-bar">
                                    <div className="progress" style={{ width: '30%' }}></div>
                                </div>
                                <button className="volume-btn">🔊</button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </DashboardLayout>
    );
};

export default VideoFeedPage;
