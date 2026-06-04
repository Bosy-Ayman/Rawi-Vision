import React, { useState, useEffect } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { searchAPI } from '../api/search';
import './SmartSearch.css';

const SmartSearch = () => {
    const [query, setQuery] = useState('');
    const [videos, setVideos] = useState([]);
    const [selectedVideo, setSelectedVideo] = useState('');
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        // Fetch videos for the dropdown
        searchAPI.listVideos()
            .then(data => {
                const completed = data.videos ? data.videos.filter(v => v.status === 'completed') : data.filter(v => v.status === 'completed');
                setVideos(completed);
                if (completed.length > 0) {
                    setSelectedVideo(completed[0].video_id);
                }
            })
            .catch(err => console.error("Failed to load videos for search", err));
    }, []);

    const handleSearch = async () => {
        if (!query.trim()) return;
        if (!selectedVideo) {
            setError("Please select a completed video to search in.");
            return;
        }

        setLoading(true);
        setError(null);
        setResults(null);

        try {
            const data = await searchAPI.querySearch(query, selectedVideo, 10, true);
            setResults(data);
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
                    <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
                        <select 
                            value={selectedVideo} 
                            onChange={(e) => setSelectedVideo(e.target.value)}
                            className="video-select"
                        >
                            <option value="">-- Select a Video to Search --</option>
                            {videos.map(v => (
                                <option key={v.video_id} value={v.video_id}>{v.filename}</option>
                            ))}
                        </select>
                    </div>
                    
                    <div className="search-input-wrapper">
                        <div className="search-icon-placeholder">
                            <img src="/assets/icons/search-icon.svg" alt="Search" style={{ width: '24px', height: '24px', opacity: 0.5 }} />
                        </div>
                        <input
                            type="text"
                            className="smart-search-input"
                            placeholder="Search by context or description... e.g. 'person in red shirt'"
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
                        {results.llm_answer && (
                            <div className="llm-answer-box">
                                <h3>AI Summary</h3>
                                <p>{results.llm_answer}</p>
                            </div>
                        )}

                        <h3 style={{marginTop: '30px', color: '#1e293b'}}>Matches ({results.total_results})</h3>
                        <div className="results-grid">
                            {results.results.map((match, idx) => (
                                <div key={idx} className="result-card">
                                    {match.clip_url ? (
                                        <video src={match.clip_url} controls className="result-video" autoPlay muted loop />
                                    ) : (
                                        <div className="no-video-placeholder">Generating Clip...</div>
                                    )}
                                    <div className="result-info">
                                        <span className="similarity-badge">{(match.similarity * 100).toFixed(1)}% Match</span>
                                        <p className="timestamp-badge">⏱ {match.timestamp.toFixed(1)}s</p>
                                        <p className="result-desc">{match.description.substring(0, 100)}...</p>
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
