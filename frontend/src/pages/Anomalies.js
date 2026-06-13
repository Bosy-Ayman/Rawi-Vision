import React, { useEffect, useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { anomalyAPI } from '../api/anomalies';
import ToastNotification from '../components/modals/ToastNotification';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from 'recharts';
import './Anomalies.css';

const WS_URL = 'ws://127.0.0.1:8001/anomalies/ws/live';

function timeAgo(isoString) {
    const diff = Math.floor((Date.now() - new Date(isoString)) / 1000);
    if (diff < 60) return `${diff} s econds ago`;
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

const CHART_COLORS = ['#dc2626', '#ea580c', '#d97706', '#7c3aed', '#6b7280'];

const Anomalies = () => {
    const [anomalies, setAnomalies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [notification, setNotification] = useState(null);
    
    // Filters
    const [selectedType, setSelectedType] = useState('All');
    const [selectedTime, setSelectedTime] = useState('All Time');

    // Selection State
    const [isSelectMode, setIsSelectMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState(new Set());

    // Load historical anomalies on mount using the existing apiClient
    useEffect(() => {
        fetchAnomalies();
    }, []);

    const fetchAnomalies = () => {
        setLoading(true);
        anomalyAPI.getAnomalies()
            .then((data) => {
                setAnomalies(data);
                setLoading(false);
            })
            .catch((err) => {
                setError(err.detail || 'Failed to load anomalies.');
                setLoading(false);
            });
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (!window.confirm('Are you sure you want to remove this anomaly?')) return;
        try {
            await anomalyAPI.deleteAnomaly(id);
            setAnomalies(prev => prev.filter(a => a.id !== id));
        } catch (err) {
            console.error("Failed to delete anomaly", err);
            alert("Failed to delete anomaly.");
        }
    };

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
                        if (prev.some(a => a.id === newAnomaly.id)) {
                            isDuplicate = true;
                            return prev;
                        }
                        return [newAnomaly, ...prev];
                    });

                    if (!isDuplicate) {
                        console.log('[WS] Triggering notification UI for:', newAnomaly.id);
                        setNotification(newAnomaly);
                        setTimeout(() => {
                            if (isComponentMounted) setNotification(null);
                        }, 7000);
                    }
                } catch (e) {
                    console.warn('[WS] Could not parse message:', event.data, e);
                }
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

    // Filter anomalies based on selection
    const filteredAnomalies = anomalies.filter(anom => {
        // Type filter
        if (selectedType !== 'All' && anom.anomaly_type !== selectedType) {
            return false;
        }

        // Time filter
        if (selectedTime !== 'All Time' && anom.detected_at) {
            const anomTime = new Date(anom.detected_at).getTime();
            const now = Date.now();
            if (selectedTime === 'Last 24 Hours' && now - anomTime > 24 * 60 * 60 * 1000) return false;
            if (selectedTime === 'Last 7 Days' && now - anomTime > 7 * 24 * 60 * 60 * 1000) return false;
        }

        return true;
    });

    const handleSelectAll = () => {
        if (selectedIds.size === filteredAnomalies.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredAnomalies.map(a => a.id)));
        }
    };

    const toggleSelection = (id) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
        }
        setSelectedIds(newSet);
    };

    const handleBulkDelete = async () => {
        if (selectedIds.size === 0) return;
        if (!window.confirm(`Are you sure you want to delete ${selectedIds.size} selected anomalies?`)) return;

        try {
            await anomalyAPI.bulkDelete(Array.from(selectedIds));
            setAnomalies(prev => prev.filter(a => !selectedIds.has(a.id)));
            setSelectedIds(new Set());
            setIsSelectMode(false);
        } catch (err) {
            console.error("Bulk delete failed", err);
            alert("Failed to delete selected anomalies.");
        }
    };

    const handleDeleteAll = async () => {
        if (!window.confirm(`WARNING: Are you sure you want to delete ALL anomalies in the database? This cannot be undone.`)) return;

        try {
            await anomalyAPI.deleteAll();
            setAnomalies([]);
            setSelectedIds(new Set());
            setIsSelectMode(false);
        } catch (err) {
            console.error("Delete all failed", err);
            alert("Failed to delete all anomalies.");
        }
    };

    const uniqueTypes = ['All', ...new Set(anomalies.map(a => a.anomaly_type).filter(Boolean))];

    // Analytics calculations based on FILTERED anomalies
    const typeDistribution = Object.entries(
        filteredAnomalies.reduce((acc, curr) => {
            const t = curr.anomaly_type || 'unknown';
            acc[t] = (acc[t] || 0) + 1;
            return acc;
        }, {})
    ).map(([name, value]) => ({ name, value }));

    const hourlyDistribution = (() => {
        const hours = Array(24).fill(0).map((_, i) => ({ name: `${i}:00`, count: 0 }));
        filteredAnomalies.forEach(anom => {
            if (anom.detected_at) {
                const hour = new Date(anom.detected_at).getHours();
                hours[hour].count += 1;
            }
        });
        return hours.filter(h => h.count > 0);
    })();

    return (
        <DashboardLayout title="Anomalies">
            {/* Live Anomaly Notification Toast */}
            {notification && (
                <div onClick={() => {
                    // Optional: scroll to the top or open modal if implemented
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                    setNotification(null);
                }} style={{ cursor: 'pointer' }}>
                    <ToastNotification 
                        type="error"
                        title="Anomaly Detected"
                        subtitle={notification.anomaly_type}
                        message={notification.description || 'Unknown event detected. Click to view.'}
                        onClose={() => setNotification(null)}
                    />
                </div>
            )}
            
            <div className="anomalies-container">
                {/* Visual Analytics Row */}
                {!loading && !error && anomalies.length > 0 && (
                    <div className="anomalies-analytics-row">
                        <div className="analytics-card">
                            <h3>Anomaly Types Distribution</h3>
                            <div className="chart-container-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie 
                                            data={typeDistribution} 
                                            cx="50%" 
                                            cy="50%" 
                                            innerRadius={60} 
                                            outerRadius={90} 
                                            paddingAngle={5} 
                                            dataKey="value"
                                        >
                                            {typeDistribution.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="analytics-card">
                            <h3>Hourly Occurrences Today</h3>
                            <div className="chart-container-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={hourlyDistribution}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
                                        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
                                        <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                                        <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Events Count" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}

                {/* Filters Row */}
                {!loading && !error && (
                    <div className="anomalies-filters">
                        <div className="filter-group">
                            <label>Time Range:</label>
                            <select value={selectedTime} onChange={(e) => setSelectedTime(e.target.value)}>
                                <option value="All Time">All Time</option>
                                <option value="Last 24 Hours">Last 24 Hours</option>
                                <option value="Last 7 Days">Last 7 Days</option>
                            </select>
                        </div>
                        <div className="filter-group">
                            <label>Anomaly Type:</label>
                            <select value={selectedType} onChange={(e) => setSelectedType(e.target.value)}>
                                {uniqueTypes.map(type => (
                                    <option key={type} value={type}>{type}</option>
                                ))}
                            </select>
                        </div>
                        <div className="filter-group" style={{ marginLeft: 'auto', display: 'flex', gap: '10px' }}>
                            {isSelectMode ? (
                                <>
                                    <button className="btn-secondary" onClick={handleSelectAll}>
                                        {selectedIds.size === filteredAnomalies.length && filteredAnomalies.length > 0 ? 'Deselect All' : 'Select All'}
                                    </button>
                                    <button className="btn-danger" onClick={handleBulkDelete} disabled={selectedIds.size === 0}>
                                        Delete Selected ({selectedIds.size})
                                    </button>
                                    <button className="btn-secondary" onClick={() => { setIsSelectMode(false); setSelectedIds(new Set()); }}>
                                        Cancel
                                    </button>
                                </>
                            ) : (
                                <>
                                    <button className="btn-secondary" onClick={() => setIsSelectMode(true)}>
                                        Select Multiple
                                    </button>
                                    <button className="btn-danger" onClick={handleDeleteAll}>
                                        Delete All Records
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                )}

                {loading && <p style={{ color: '#9ca3af' }}>Loading anomalies...</p>}
                {error && <p style={{ color: '#ef4444' }}>Error: {error}</p>}
                {!loading && !error && filteredAnomalies.length === 0 && (
                    <div className="anomalies-empty-state">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                        <h3>No anomalies found</h3>
                        <p>No records match your selected filters.</p>
                    </div>
                )}
                
                <div className="anomalies-grid">
                    {filteredAnomalies.map((item) => (
                        <div 
                            key={item.id} 
                            className={`anomaly-card ${isSelectMode && selectedIds.has(item.id) ? 'selected' : ''}`}
                            onClick={() => {
                                if (isSelectMode) toggleSelection(item.id);
                            }}
                            style={isSelectMode ? { cursor: 'pointer', outline: selectedIds.has(item.id) ? '3px solid #3b82f6' : 'none' } : {}}
                        >
                            {/* Checkbox for Select Mode */}
                            {isSelectMode && (
                                <input 
                                    type="checkbox" 
                                    className="anomaly-checkbox"
                                    checked={selectedIds.has(item.id)}
                                    readOnly
                                />
                            )}

                            {/* Delete Button (hidden in select mode) */}
                            {!isSelectMode && (
                                <button 
                                    className="anomaly-delete-btn" 
                                    onClick={(e) => handleDelete(item.id, e)}
                                    title="Remove this anomaly"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                </button>
                            )}

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
