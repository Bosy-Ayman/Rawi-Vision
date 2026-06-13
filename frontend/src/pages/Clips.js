import React, { useState, useEffect, useRef } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { searchAPI } from '../api/search';
import { BASE_URL } from '../api/client';
import './Clips.css';

const Clips = () => {
    const [videos, setVideos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    
    // Timeline modal state
    const [selectedVideo, setSelectedVideo] = useState(null);
    const [frames, setFrames] = useState([]);
    const [loadingFrames, setLoadingFrames] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [searchTermTimeline, setSearchTermTimeline] = useState('');
    
    const [activeRecordings, setActiveRecordings] = useState([]);
    const [ticker, setTicker] = useState(0);
    
    // Filter & Sort State
    const [searchTerm, setSearchTerm] = useState('');
    const [filterSource, setFilterSource] = useState('all'); // all, camera, upload
    const [filterCamera, setFilterCamera] = useState('all');
    const [sortBy, setSortBy] = useState('newest');
    
    const videoRef = useRef(null);

    useEffect(() => {
        fetchVideos();
    }, []);

    // Force re-render every second to update recording duration timer
    useEffect(() => {
        const timer = setInterval(() => {
            setTicker(t => t + 1);
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    // Set up polling interval to fetch clips list and active recordings status
    useEffect(() => {
        const interval = setInterval(() => {
            fetchVideos();
        }, 3000);

        return () => clearInterval(interval);
    }, []);

    const fetchVideos = async () => {
        try {
            const [videosData, activeData] = await Promise.all([
                searchAPI.listVideos(),
                searchAPI.getActiveRecordings()
            ]);
            setVideos(Array.isArray(videosData) ? videosData : (videosData.videos || []));
            setActiveRecordings(Array.isArray(activeData) ? activeData : []);
        } catch (err) {
            console.error("Failed to fetch videos", err);
        } finally {
            setLoading(false);
        }
    };

    const handleStopRecording = async (cameraId) => {
        try {
            await searchAPI.stopRecording(cameraId);
            setActiveRecordings(prev => prev.filter(r => r.camera_id !== cameraId));
            alert("Stop signal sent. Recording will finish, upload the final chunk, and begin indexing shortly.");
            setTimeout(fetchVideos, 1500); // quick refresh
        } catch (err) {
            console.error("Failed to stop recording", err);
            alert("Failed to stop recording.");
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

    const handleOpenTimeline = async (video) => {
        setSelectedVideo(video);
        setCurrentTime(0);
        setSearchTermTimeline('');
        setLoadingFrames(true);
        try {
            const data = await searchAPI.getVideoFrames(video.video_id);
            setFrames(data);
        } catch (err) {
            console.error("Failed to load video frames", err);
            setFrames([]);
        } finally {
            setLoadingFrames(false);
        }
    };

    const handleCloseTimeline = () => {
        setSelectedVideo(null);
        setFrames([]);
        setCurrentTime(0);
        setSearchTermTimeline('');
    };

    const handleSeekToFrame = (timestamp) => {
        if (videoRef.current) {
            videoRef.current.currentTime = timestamp;
            videoRef.current.play().catch(() => {});
        }
    };

    const formatTimestamp = (secs) => {
        const minutes = Math.floor(secs / 60);
        const seconds = Math.floor(secs % 60);
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    };

    const getElapsedTimeString = (startTime) => {
        if (!startTime) return '00:00';
        const elapsedSecs = Math.max(0, Math.floor(Date.now() / 1000) - startTime);
        const mins = Math.floor(elapsedSecs / 60);
        const secs = elapsedSecs % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    const parseDescription = (desc) => {
        if (!desc) return { text: '', tags: [] };
        const parts = desc.split('|').map(p => p.trim());
        const text = parts[0];
        const tags = [];
        
        parts.slice(1).forEach(part => {
            if (part.startsWith('Objects:')) {
                let objText = part.replace('Objects:', '').trim();
                objText = objText.split(', with detected text:')[0].trim();
                if (objText && objText.toLowerCase() !== 'none') {
                    tags.push({ label: 'Objects', value: objText, type: 'objects' });
                }
            } else if (part.startsWith('Motion:')) {
                const motionText = part.replace('Motion:', '').trim();
                if (motionText && motionText.toLowerCase() !== 'none') {
                    tags.push({ label: 'Motion', value: motionText, type: 'motion' });
                }
            } else if (part.startsWith('Text detected:')) {
                const textVal = part.replace('Text detected:', '').trim();
                if (textVal && textVal.toLowerCase() !== 'none') {
                    tags.push({ label: 'Text', value: textVal, type: 'text' });
                }
            } else {
                tags.push({ label: 'Info', value: part, type: 'info' });
            }
        });
        
        return { text, tags };
    };

    // Calculate active frame index based on current playback time
    const activeFrameIndex = frames.reduce((bestIndex, frame, index) => {
        if (frame.timestamp_offset <= currentTime && frame.timestamp_offset > (frames[bestIndex]?.timestamp_offset || -1)) {
            return index;
        }
        return bestIndex;
    }, -1);

    // Auto-scroll active timeline item into view
    useEffect(() => {
        if (selectedVideo && activeFrameIndex !== -1) {
            const activeEl = document.querySelector('.timeline-item.active');
            if (activeEl) {
                activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    }, [activeFrameIndex, selectedVideo]);

    const availableCameras = Array.from(
        new Set(videos.map(v => v.camera_number).filter(Boolean))
    ).sort();

    let processedVideos = [...videos];

    // 1. Filter by Search term (filename)
    if (searchTerm) {
        processedVideos = processedVideos.filter(v => 
            v.filename.toLowerCase().includes(searchTerm.toLowerCase())
        );
    }

    // 2. Filter by Source Type (recorded vs uploaded)
    if (filterSource === 'camera') {
        processedVideos = processedVideos.filter(v => v.camera_number !== null && v.camera_number !== undefined);
    } else if (filterSource === 'upload') {
        processedVideos = processedVideos.filter(v => !v.camera_number);
    }

    // 3. Filter by Camera Number
    if (filterSource !== 'upload' && filterCamera !== 'all') {
        processedVideos = processedVideos.filter(v => v.camera_number === filterCamera);
    }

    // 4. Sort
    processedVideos.sort((a, b) => {
        if (sortBy === 'newest') {
            return new Date(b.date_created) - new Date(a.date_created);
        } else if (sortBy === 'oldest') {
            return new Date(a.date_created) - new Date(b.date_created);
        } else if (sortBy === 'name') {
            return a.filename.localeCompare(b.filename);
        }
        return 0;
    });

    return (
        <DashboardLayout title="Video Clips Library">
            <div className="clips-container">
                <div className="clips-header">
                    <div className="clips-header-left">
                        <h2>Clips Library</h2>
                        <p>Manage recorded and uploaded video clips for AI indexing and security analysis.</p>
                    </div>
                    <div className="upload-btn-wrapper">
                        <button className="upload-btn" disabled={uploading}>
                            {uploading ? 'Uploading...' : '📤 Upload Video (.mp4)'}
                        </button>
                        <input type="file" accept="video/mp4,video/x-m4v,video/*" onChange={handleUpload} />
                    </div>
                </div>

                <div className="clips-stats-row">
                    <div className="stat-card" style={{ '--stat-accent': 'linear-gradient(90deg, #6c5ce7, #a29bfe)' }}>
                        <span className="stat-icon">🎞️</span>
                        <div className="stat-info">
                            <span className="stat-value">{videos.length}</span>
                            <span className="stat-label">Total Clips</span>
                        </div>
                    </div>
                    <div className="stat-card" style={{ '--stat-accent': 'linear-gradient(90deg, #10b981, #34d399)' }}>
                        <span className="stat-icon">✅</span>
                        <div className="stat-info">
                            <span className="stat-value">{videos.filter(v => v.status === 'completed').length}</span>
                            <span className="stat-label">Indexed</span>
                        </div>
                    </div>
                    <div className="stat-card" style={{ '--stat-accent': 'linear-gradient(90deg, #3b82f6, #60a5fa)' }}>
                        <span className="stat-icon">⚡</span>
                        <div className="stat-info">
                            <span className="stat-value">{videos.filter(v => v.status === 'indexing' || v.status === 'pending').length}</span>
                            <span className="stat-label">Indexing</span>
                        </div>
                    </div>
                    <div className="stat-card" style={{ '--stat-accent': 'linear-gradient(90deg, #ef4444, #f87171)' }}>
                        <span className="stat-icon">⚠️</span>
                        <div className="stat-info">
                            <span className="stat-value">{videos.filter(v => v.status === 'failed').length}</span>
                            <span className="stat-label">Failed</span>
                        </div>
                    </div>
                </div>

                {activeRecordings.length > 0 && (
                    <div className="active-recordings-panel">
                        <div className="active-rec-header">
                            <span className="live-rec-dot" />
                            <h3>Active AI Camera Recordings</h3>
                        </div>
                        <div className="active-rec-list">
                            {activeRecordings.map((rec) => (
                                <div key={rec.camera_id} className="active-rec-item">
                                    <div className="active-rec-info">
                                        <span className="active-rec-camera">
                                            📹 {rec.camera_number || 'Camera'} ({rec.camera_room || 'Room'} - {rec.camera_building || 'Building'})
                                        </span>
                                        <span className="active-rec-status-badge">
                                            <span className="live-rec-dot" style={{ width: '8px', height: '8px', margin: 0 }} />
                                            RECORDING ({getElapsedTimeString(rec.start_time)})
                                        </span>
                                        <span className="active-rec-chunks">
                                            • Chunks Captured: <strong>{rec.chunks_recorded}</strong>
                                        </span>
                                        <span className="active-rec-time">
                                            • Started: {new Date(rec.start_time * 1000).toLocaleTimeString()}
                                        </span>
                                    </div>
                                    <button 
                                        onClick={() => handleStopRecording(rec.camera_id)} 
                                        className="stop-rec-btn-clips"
                                    >
                                        ⏹ Stop Recording
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                <div className="clips-filter-bar">
                    <div className="filter-group search-group">
                        <span className="filter-label">Search Filename</span>
                        <input 
                            type="text" 
                            placeholder="Search clips..." 
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="filter-input search-input"
                        />
                    </div>
                    
                    <div className="filter-group">
                        <span className="filter-label">Source Type</span>
                        <select 
                            value={filterSource}
                            onChange={(e) => {
                                setFilterSource(e.target.value);
                                if (e.target.value === 'upload') {
                                    setFilterCamera('all');
                                }
                            }}
                            className="filter-select"
                        >
                            <option value="all">All Sources</option>
                            <option value="camera">📹 Camera Recordings</option>
                            <option value="upload">📂 Manual Uploads</option>
                        </select>
                    </div>

                    {filterSource !== 'upload' && (
                        <div className="filter-group">
                            <span className="filter-label">Camera Number</span>
                            <select 
                                value={filterCamera}
                                onChange={(e) => setFilterCamera(e.target.value)}
                                className="filter-select"
                            >
                                <option value="all">All Cameras</option>
                                {availableCameras.map(cam => (
                                    <option key={cam} value={cam}>{cam}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div className="filter-group">
                        <span className="filter-label">Sort By</span>
                        <select 
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value)}
                            className="filter-select"
                        >
                            <option value="newest">📅 Newest First</option>
                            <option value="oldest">📅 Oldest First</option>
                            <option value="name">🔤 Filename (A-Z)</option>
                        </select>
                    </div>
                </div>
                
                {loading ? (
                    <div className="clips-loading-spinner-container">
                        <div className="loading-spinner-large" />
                        <p>Loading clips library...</p>
                    </div>
                ) : (
                    <div className="insights-grid">
                        {processedVideos.map((video) => (
                            <div key={video.video_id} className="insight-card">
                                <div className="insight-image-placeholder" style={{ padding: 0, overflow: 'hidden', backgroundColor: '#000' }}>
                                    <div className="card-badge-overlay">
                                        <span className={`status-pill ${video.status}`}>
                                            {video.status === 'completed' && '● '}
                                            {video.status === 'indexing' && '⚡ '}
                                            {video.status === 'pending' && '⏳ '}
                                            {video.status === 'failed' && '⚠️ '}
                                            {video.status.toUpperCase()}
                                        </span>
                                    </div>
                                    
                                    {video.status === 'completed' ? (
                                        <div className="completed-video-container" style={{ width: '100%', height: '100%', position: 'relative' }}>
                                            <video 
                                                src={`${BASE_URL}/api/search/video/${video.video_id}/stream`}
                                                controls
                                                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                                            />
                                        </div>
                                    ) : (
                                        <div className={`video-status-overlay ${video.status === 'indexing' ? 'indexing-mode' : ''}`}>
                                            {video.status === 'indexing' && (
                                                <div className="indexing-progress-container">
                                                    <div className="loading-spinner-small" />
                                                    <div className="progress-bar-bg">
                                                        <div 
                                                            className="progress-bar-fill" 
                                                            style={{ width: `${video.progress_percent || 0}%` }}
                                                        />
                                                    </div>
                                                    <span className="progress-text">
                                                        Indexing... {video.progress_percent || 0}%
                                                    </span>
                                                </div>
                                            )}
                                            {video.status === 'pending' && (
                                                <div className="pending-state-container">
                                                    <div className="loading-spinner-small" />
                                                    <span className="pending-text">Waiting in queue...</span>
                                                </div>
                                            )}
                                            {video.status === 'failed' && (
                                                <div className="failed-state-container">
                                                    <span className="failed-icon">❌</span>
                                                    <span className="failed-text">Indexing Failed</span>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                                <div className="insight-content" style={{ position: 'relative' }}>
                                    <div className="card-source-row">
                                        <span className={`source-tag ${video.camera_number ? 'camera-src' : 'upload-src'}`}>
                                            {video.camera_number ? `📷 ${video.camera_number}` : '📂 Manual Upload'}
                                        </span>
                                    </div>
                                    <h3 className="insight-title" style={{ fontSize: '0.95rem', fontWeight: '700', marginBottom: '8px', color: '#1e293b' }} title={video.filename}>
                                        {video.filename}
                                    </h3>
                                    <p className="insight-description" style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '16px' }}>
                                        {video.camera_number ? 'Recorded' : 'Uploaded'}: {new Date(video.date_created).toLocaleString()}
                                        {video.camera_room && ` in ${video.camera_room} (${video.camera_building})`}
                                    </p>
                                    <div className="card-actions-row" style={{ display: 'flex', gap: '8px', justifyContent: 'space-between', alignItems: 'center' }}>
                                        {video.status === 'completed' ? (
                                            <button 
                                                className="view-timeline-btn" 
                                                onClick={() => handleOpenTimeline(video)}
                                            >
                                                👁️ View AI Timeline
                                            </button>
                                        ) : (
                                            <div className="timeline-placeholder-btn">
                                                ⏳ Indexing...
                                            </div>
                                        )}
                                        <button 
                                            className="delete-clip-btn-static" 
                                            onClick={() => handleDelete(video.video_id)}
                                            title="Delete Video"
                                        >
                                            🗑️ Delete
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                {videos.length === 0 && !loading && (
                    <div className="empty-state-library">
                        <span className="empty-icon">📂</span>
                        <p>No clips found in library. Upload a file or start recording from live camera feeds.</p>
                    </div>
                )}
            </div>

            {/* AI Timeline Modal */}
            {selectedVideo && (
                <div className="timeline-modal-backdrop" onClick={handleCloseTimeline}>
                    <div className="timeline-modal-content" onClick={(e) => e.stopPropagation()}>
                        <div className="timeline-modal-header">
                            <div className="timeline-modal-title-area">
                                <h2 className="timeline-modal-title">{selectedVideo.filename}</h2>
                                {selectedVideo.camera_number && (
                                    <span className="timeline-modal-subtitle">
                                        Recorded from {selectedVideo.camera_number} ({selectedVideo.camera_room})
                                    </span>
                                )}
                            </div>
                            <button className="close-modal-btn" onClick={handleCloseTimeline}>&times;</button>
                        </div>
                        <div className="timeline-modal-body">
                            <div className="timeline-video-container">
                                <video 
                                    ref={videoRef}
                                    src={`${BASE_URL}/api/search/video/${selectedVideo.video_id}/stream`}
                                    controls
                                    className="timeline-main-video"
                                    autoPlay
                                    onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
                                />
                            </div>
                            <div className="timeline-sidebar">
                                <div className="sidebar-header-wrapper">
                                    <h3 className="sidebar-heading">AI Video Timeline</h3>
                                    <span className="timeline-badge">{frames.length} events</span>
                                </div>
                                <div className="timeline-search-box">
                                    <input 
                                        type="text" 
                                        placeholder="Filter timeline..." 
                                        value={searchTermTimeline}
                                        onChange={(e) => setSearchTermTimeline(e.target.value)}
                                        className="timeline-search-input"
                                    />
                                    {searchTermTimeline && (
                                        <button className="clear-search-btn" onClick={() => setSearchTermTimeline('')}>&times;</button>
                                    )}
                                </div>
                                {loadingFrames ? (
                                    <div className="timeline-loading">Loading AI descriptions...</div>
                                ) : frames.length === 0 ? (
                                    <div className="timeline-empty">No frame descriptions indexed.</div>
                                ) : (
                                    <div className="timeline-list">
                                        <div className="timeline-list-track">
                                            {frames
                                                .map((frame, index) => ({ ...frame, originalIndex: index }))
                                                .filter(frame => frame.description.toLowerCase().includes(searchTermTimeline.toLowerCase()))
                                                .map((frame) => {
                                                    const isActive = frame.originalIndex === activeFrameIndex;
                                                    return (
                                                        <div 
                                                            key={frame.originalIndex} 
                                                            className={`timeline-item ${isActive ? 'active' : ''}`}
                                                            onClick={() => handleSeekToFrame(frame.timestamp_offset)}
                                                        >
                                                            <div className="timeline-dot-connector">
                                                                <div className={`timeline-dot ${isActive ? 'active' : ''}`} />
                                                            </div>
                                                            <div className="timeline-item-content">
                                                                <div className="timeline-item-time">
                                                                    <span className="play-icon">▶</span>
                                                                    <span>{formatTimestamp(frame.timestamp_offset)}</span>
                                                                </div>
                                                                <div className="timeline-item-desc">
                                                                    {(() => {
                                                                        const parsed = parseDescription(frame.description);
                                                                        return (
                                                                            <>
                                                                                <div className="timeline-desc-text">{parsed.text}</div>
                                                                                {parsed.tags.length > 0 && (
                                                                                    <div className="timeline-tags-row">
                                                                                        {parsed.tags.map((tag, tIdx) => (
                                                                                            <span key={tIdx} className={`timeline-tag ${tag.type}`}>
                                                                                                <strong>{tag.label}:</strong> {tag.value}
                                                                                            </span>
                                                                                        ))}
                                                                                    </div>
                                                                                )}
                                                                            </>
                                                                        );
                                                                    })()}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default Clips;
