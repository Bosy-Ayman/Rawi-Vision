import React, { useState, useEffect, useRef, useMemo } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { searchAPI } from '../api/search';
import './SmartSearch.css';

const BACKEND_BASE = 'http://127.0.0.1:8001';

// --------------------------------------------------------------------
// ClipPlayer: polls /api/search/clip-status until the clip is ready
// --------------------------------------------------------------------
const ClipPlayer = ({ clipPath }) => {
    const [clipSrc, setClipSrc] = useState(null);
    const [status, setStatus] = useState('loading'); // loading | ready | error
    const intervalRef = useRef(null);

    useEffect(() => {
        if (!clipPath) { setStatus('error'); return; }

        // clipPath is like /api/search/clip/{video_id}/{frame}?timestamp=X
        // Build the corresponding status URL
        const statusUrl = `${BACKEND_BASE}${clipPath.replace('/api/search/clip/', '/api/search/clip-status/')}`;
        const fullClipUrl = `${BACKEND_BASE}${clipPath}`;

        const checkReady = async () => {
            try {
                const res = await fetch(statusUrl);
                if (res.ok) {
                    const data = await res.json();
                    if (data.ready) {
                        clearInterval(intervalRef.current);
                        setClipSrc(fullClipUrl);
                        setStatus('ready');
                    }
                    // not ready yet — keep polling
                }
            } catch {
                // network error — keep trying
            }
        };

        checkReady();
        intervalRef.current = setInterval(checkReady, 3000);

        return () => clearInterval(intervalRef.current);
    }, [clipPath]);

    if (status === 'ready' && clipSrc) {
        return (
            <video
                src={clipSrc}
                controls
                className="result-video"
                autoPlay
                muted
                loop
                onError={() => setStatus('error')}
            />
        );
    }

    if (status === 'error') {
        return <div className="no-video-placeholder">⚠ Clip unavailable</div>;
    }

    return (
        <div className="no-video-placeholder generating">
            <span className="spinner" />
            Generating clip…
        </div>
    );
};

// --------------------------------------------------------------------
// DescriptionBlock: parses pipe-separated VLM description into sections
// --------------------------------------------------------------------
const DescriptionBlock = ({ text }) => {
    if (!text) return null;

    const parts = text.split('|').map(s => s.trim());
    const mainDesc = parts[0] || '';

    const getSection = (label) => {
        const part = parts.find(p => p.toLowerCase().startsWith(label.toLowerCase()));
        if (!part) return null;
        return part.substring(part.indexOf(':') + 1).trim();
    };

    const objects = getSection('Objects');
    const motion  = getSection('Motion');
    const textDet = getSection('Text detected');

    // Cut off at "with detected text" before splitting — keeps only YOLO labels
    const objectsRaw = objects || '';
    const cutIdx = objectsRaw.toLowerCase().indexOf('with detected text');
    const pureObjects = cutIdx >= 0 ? objectsRaw.substring(0, cutIdx) : objectsRaw;
    
    // Filter: only real words (>= 2 chars, alphanumeric)
    const objectList = pureObjects
        .split(',')
        .map(o => o.trim())
        .filter(o => o.length >= 2 && /^[a-zA-Z0-9 _-]+$/.test(o));

    return (
        <div className="desc-block">
            <p className="desc-main">{mainDesc}</p>

            {objectList.length > 0 && (
                <div className="desc-row">
                    <span className="desc-icon">📦</span>
                    <div className="desc-tags">
                        {objectList.map((obj, i) => (
                            <span key={i} className="desc-tag">{obj}</span>
                        ))}
                    </div>
                </div>
            )}

            {motion && (
                <div className="desc-row">
                    <span className="desc-icon">🎬</span>
                    <span className="desc-motion">{motion}</span>
                </div>
            )}

            {textDet && textDet !== 'no text' && (
                <div className="desc-row">
                    <span className="desc-icon">🔤</span>
                    <span className="desc-ocr">{textDet}</span>
                </div>
            )}
        </div>
    );
};

const SmartSearch = () => {
    const [query, setQuery] = useState('');
    const [videos, setVideos] = useState([]);
    const [selectedVideos, setSelectedVideos] = useState([]);
    const [selectedCameraFilter, setSelectedCameraFilter] = useState('all');
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [startTime, setStartTime] = useState('');
    const [endTime, setEndTime] = useState('');
    const dropdownRef = useRef(null);

    const availableCameras = Array.from(
        new Set(videos.map(v => v.camera_number).filter(Boolean))
    ).sort();

    const filteredVideos = useMemo(() => {
        return videos.filter(video => {
            if (selectedCameraFilter !== 'all') {
                if (selectedCameraFilter === 'upload') {
                    if (video.camera_number) return false;
                } else {
                    if (video.camera_number !== selectedCameraFilter) return false;
                }
            }

            if (!video.date_created) return true;
            const videoDate = new Date(video.date_created);

            if (startDate) {
                const start = new Date(`${startDate}T${startTime || '00:00'}:00`);
                if (videoDate < start) return false;
            }
            if (endDate) {
                const end = new Date(`${endDate}T${endTime || '23:59'}:59`);
                if (videoDate > end) return false;
            }
            return true;
        });
    }, [videos, selectedCameraFilter, startDate, endDate, startTime, endTime]);

    // Auto-select matching videos when filters change
    useEffect(() => {
        setSelectedVideos(filteredVideos.map(v => v.video_id));
    }, [filteredVideos]);

    const activeVideosToSearch = selectedVideos.filter(id => filteredVideos.some(v => v.video_id === id));

    const getDropdownLabel = () => {
        if (filteredVideos.length === 0) return "No videos available";
        const activeCount = activeVideosToSearch.length;
        if (activeCount === 0) return "No videos selected";
        if (activeCount === filteredVideos.length) return "All videos selected";
        return `${activeCount} of ${filteredVideos.length} video(s) selected`;
    };

    const formatVideoLabel = (video) => {
        if (!video.date_created) return video.filename;
        const date = new Date(video.date_created);
        const dateString = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        const timeString = date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        return `${video.filename} (${dateString} ${timeString})`;
    };

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    useEffect(() => {
        // Fetch videos for the dropdown
        searchAPI.listVideos()
            .then(data => {
                const completed = data.videos ? data.videos.filter(v => v.status === 'completed') : data.filter(v => v.status === 'completed');
                setVideos(completed);
                if (completed.length > 0) {
                    setSelectedVideos(completed.map(v => v.video_id));
                }
            })
            .catch(err => console.error("Failed to load videos for search", err));
    }, []);

    const handleSearch = async () => {
        if (!query.trim()) return;
        if (activeVideosToSearch.length === 0) {
            setError("Please select at least one completed video to search in.");
            return;
        }

        setLoading(true);
        setError(null);
        setResults(null);

        try {
            // Run parallel searches for all active videos
            const searchPromises = activeVideosToSearch.map(async (videoId) => {
                const video = videos.find(v => v.video_id === videoId);
                const videoLabel = video ? video.filename : 'Unknown Video';
                try {
                    const data = await searchAPI.querySearch(query, videoId, 10, true);
                    // Attach video context to each match
                    const enrichedMatches = (data.results || []).map(match => ({
                        ...match,
                        videoId: videoId,
                        videoName: videoLabel
                    }));
                    return {
                        ...data,
                        results: enrichedMatches,
                        videoName: videoLabel
                    };
                } catch (err) {
                    console.error(`Search failed for video ${videoLabel}:`, err);
                    return {
                        query: query,
                        total_results: 0,
                        results: [],
                        reid_tracks: {},
                        llm_answer: `Search failed: ${err.message || err.detail || 'Unknown error'}`
                    };
                }
            });

            const allResults = await Promise.all(searchPromises);

            // Merge and sort results
            const mergedResults = [];
            allResults.forEach(res => {
                mergedResults.push(...res.results);
            });

            // Sort by similarity descending
            mergedResults.sort((a, b) => b.similarity - a.similarity);

            // Combine LLM answers
            const llmAnswers = allResults
                .filter(res => res.llm_answer && res.llm_answer !== "No matching events or objects found in this video." && res.llm_answer !== "Local LLM reasoning unavailable.")
                .map(res => ({
                    videoName: res.videoName,
                    answer: res.llm_answer
                }));

            const hasMatches = mergedResults.length > 0;
            let finalLlmAnswer = null;
            if (!hasMatches) {
                finalLlmAnswer = "No matching events or objects found in the selected videos.";
            }

            // Merge Re-ID tracks
            const mergedReidTracks = {};
            allResults.forEach(res => {
                if (res.reid_tracks) {
                    Object.entries(res.reid_tracks).forEach(([trackName, appearances]) => {
                        mergedReidTracks[`${res.videoName} - ${trackName}`] = appearances;
                    });
                }
            });

            setResults({
                query: query,
                total_results: mergedResults.length,
                results: mergedResults,
                reid_tracks: mergedReidTracks,
                llm_answers: llmAnswers,
                llm_answer: finalLlmAnswer
            });
        } catch (err) {
            console.error(err);
            setError(err.detail || "Search failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardLayout title="Smart Search">
            <div className="smart-search-container">
                {/* Icons Row */}
                <div className="search-icons-row">
                    <div className="search-feature-icon">
                        <img src="/assets/icons/attendance_icon.svg" alt="Person" />
                    </div>
                    <div className="search-feature-icon active">
                        <img src="/assets/icons/summarization-icon.svg" alt="Document" />
                    </div>
                    <div className="search-feature-icon">
                        <img src="/assets/icons/search-icon.svg" alt="Search" />
                    </div>
                </div>

                {/* Tagline */}
                <h2 className="search-tagline">LOOK INTO VIDEOS EVENTS AND MUCH MORE !!</h2>

                {/* Search Box Card */}
                <div className="search-card">
                    {/* Step 1: Configuration (Video selection & Time filters) */}
                    <div className="search-config-grid">
                        <div className="config-item camera-filter-group">
                            <label className="config-label">📹 Camera Filter</label>
                            <select
                                className="video-select"
                                value={selectedCameraFilter}
                                onChange={(e) => setSelectedCameraFilter(e.target.value)}
                            >
                                <option value="all">All Sources</option>
                                <option value="upload">📂 Manual Uploads</option>
                                {availableCameras.map(cam => (
                                    <option key={cam} value={cam}>📹 {cam}</option>
                                ))}
                            </select>
                        </div>

                        <div className="config-item video-selection-group" ref={dropdownRef}>
                            <label className="config-label">📁 Video Streams</label>
                            <div className="multi-select-container">
                                <button
                                    type="button"
                                    className="dropdown-toggle"
                                    onClick={() => setDropdownOpen(!dropdownOpen)}
                                >
                                    <span>{getDropdownLabel()}</span>
                                    <span className="dropdown-arrow">▼</span>
                                </button>
                                {dropdownOpen && (
                                    <div className="dropdown-menu">
                                        {filteredVideos.length > 0 ? (
                                            <>
                                                <div className="dropdown-actions">
                                                    <button
                                                        type="button"
                                                        className="dropdown-action-btn"
                                                        onClick={() => setSelectedVideos(filteredVideos.map(v => v.video_id))}
                                                    >
                                                        Select All
                                                    </button>
                                                    <button
                                                        type="button"
                                                        className="dropdown-action-btn"
                                                        onClick={() => setSelectedVideos([])}
                                                    >
                                                        Clear All
                                                    </button>
                                                </div>
                                                <div className="dropdown-items-list">
                                                    {filteredVideos.map(v => {
                                                        const isChecked = selectedVideos.includes(v.video_id);
                                                        return (
                                                            <label key={v.video_id} className="dropdown-item">
                                                                <input
                                                                    type="checkbox"
                                                                    checked={isChecked}
                                                                    onChange={() => {
                                                                        if (isChecked) {
                                                                            setSelectedVideos(selectedVideos.filter(id => id !== v.video_id));
                                                                        } else {
                                                                            setSelectedVideos([...selectedVideos, v.video_id]);
                                                                        }
                                                                    }}
                                                                />
                                                                <span className="dropdown-item-label">{formatVideoLabel(v)}</span>
                                                            </label>
                                                        );
                                                    })}
                                                </div>
                                            </>
                                        ) : (
                                            <div className="dropdown-no-items">No completed videos match the filters</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="config-item date-time-group">
                            <label className="config-label">📅 Start Window</label>
                            <div className="filter-inputs">
                                <input 
                                    type="date" 
                                    value={startDate} 
                                    onChange={(e) => setStartDate(e.target.value)} 
                                    className="filter-input"
                                />
                                <input 
                                    type="time" 
                                    value={startTime} 
                                    onChange={(e) => setStartTime(e.target.value)} 
                                    className="filter-input"
                                />
                            </div>
                        </div>

                        <div className="config-item date-time-group">
                            <label className="config-label">📅 End Window</label>
                            <div className="filter-inputs">
                                <input 
                                    type="date" 
                                    value={endDate} 
                                    onChange={(e) => setEndDate(e.target.value)} 
                                    className="filter-input"
                                />
                                <input 
                                    type="time" 
                                    value={endTime} 
                                    onChange={(e) => setEndTime(e.target.value)} 
                                    className="filter-input"
                                />
                            </div>
                        </div>

                        {(startDate || endDate || startTime || endTime || selectedCameraFilter !== 'all') && (
                            <div className="config-item reset-group">
                                <button 
                                    className="clear-filters-btn" 
                                    onClick={() => {
                                        setStartDate('');
                                        setEndDate('');
                                        setStartTime('');
                                        setEndTime('');
                                        setSelectedCameraFilter('all');
                                    }}
                                >
                                    Reset
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Step 2: Main Search Bar */}
                    <div className="search-input-wrapper">
                        <div className="search-icon-placeholder">
                            <img src="/assets/icons/search-icon.svg" alt="Search" style={{ width: '24px', height: '24px', opacity: 0.5 }} />
                        </div>
                        <input
                            type="text"
                            className="smart-search-input"
                            placeholder="Type what you want to find... e.g. 'person in red shirt' or 'running behavior'"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                        />
                        <button className="enter-btn" onClick={handleSearch} disabled={loading}>
                            {loading ? 'Searching...' : 'Enter'}
                        </button>
                    </div>
                    {error && <p className="search-error">{error}</p>}
                </div>

                {/* Results Area */}
                {results && (
                    <div className="search-results-container">
                        {results.llm_answers && results.llm_answers.length > 0 && (
                            <div className="llm-answer-box">
                                <h3>AI Summary</h3>
                                <div className="llm-answers-list">
                                    {results.llm_answers.map((ans, index) => (
                                        <div key={index} className="llm-answer-item" style={{ marginBottom: index < results.llm_answers.length - 1 ? '16px' : '0' }}>
                                            <strong style={{ color: '#166534', display: 'block', marginBottom: '4px', fontSize: '0.9rem' }}>
                                                🎥 {ans.videoName}
                                            </strong>
                                            <p style={{ margin: 0, color: '#15803d', fontSize: '0.95rem', lineHeight: '1.6' }}>{ans.answer}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {results.llm_answer && (
                            <div className="llm-answer-box">
                                <h3>AI Summary</h3>
                                <p style={{ margin: 0, color: '#15803d', fontSize: '0.95rem', lineHeight: '1.6' }}>{results.llm_answer}</p>
                            </div>
                        )}

                        <h3 style={{marginTop: '30px', color: '#1e293b'}}>Matches ({results.total_results})</h3>
                        <div className="results-grid">
                            {results.results.map((match, idx) => (
                                <div key={idx} className="result-card">
                                    <ClipPlayer clipPath={match.clip_url} />
                                    <div className="result-info">
                                        <div className="result-badges-row">
                                            <span className="similarity-badge">{match.similarity.toFixed(1)}% Match</span>
                                            <span className="timestamp-badge">⏱ {match.timestamp.toFixed(1)}s</span>
                                            {match.videoName && (
                                                <span className="video-source-badge" title={match.videoName}>
                                                    🎥 {match.videoName}
                                                </span>
                                            )}
                                        </div>
                                        <DescriptionBlock text={match.description} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default SmartSearch;
