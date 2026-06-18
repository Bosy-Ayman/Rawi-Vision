import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { anomalyAPI } from '../api/anomalies';
import { employeeAPI } from '../api/employees';
import ToastNotification from '../components/modals/ToastNotification';
import EmployeeAvatar from '../components/dashboard/EmployeeAvatar';
import {  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
import './Anomalies.css';

const WS_URL = 'ws://127.0.0.1:8002/anomalies/ws/live';

const WEEKDAYS_FULL = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

function timeAgo(isoString) {
    const diff = Math.floor((Date.now() - new Date(isoString)) / 1000);
    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
}

const BADGE_COLORS = {
    violence: 'linear-gradient(135deg, #f87171 0%, #dc2626 100%)',
    theft: 'linear-gradient(135deg, #fb923c 0%, #ea580c 100%)',
    vandalism: 'linear-gradient(135deg, #fbbf24 0%, #d97706 100%)',
    unusual_behavior: 'linear-gradient(135deg, #c084fc 0%, #7c3aed 100%)',
    out_of_bounds: 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)',
    unknown: 'linear-gradient(135deg, #9ca3af 0%, #4b5563 100%)',
};

const TYPE_EMOJIS = {
    violence: '⚠️',
    theft: '🚨',
    vandalism: '🛠️',
    unusual_behavior: '👁️',
    out_of_bounds: '🚪',
    unknown: '❓'
};

const CHART_COLORS = ['#ef4444', '#f97316', '#f59e0b', '#8b5cf6', '#0ea5e9', '#6b7280'];

const Anomalies = () => {
    const [anomalies, setAnomalies] = useState([]);
    const [employeesMap, setEmployeesMap] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [notification, setNotification] = useState(null);
    
    // Filters & Search
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedType, setSelectedType] = useState('All');
    const [selectedTime, setSelectedTime] = useState('All Time');

    // Selection State
    const [isSelectMode, setIsSelectMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState(new Set());

    // Modal State
    const [selectedAlertForModal, setSelectedAlertForModal] = useState(null);

    const location = useLocation();
    const isRoomAlertsPage = location.pathname === '/dashboard/room-alerts';

    useEffect(() => {
        const loadInitialData = async () => {
            setLoading(true);
            try {
                // Fetch employees first to resolve IDs
                let emps = [];
                try {
                    emps = await employeeAPI.getAllEmployees();
                    const empMap = {};
                    (emps || []).forEach(emp => {
                        empMap[emp.id] = emp;
                    });
                    setEmployeesMap(empMap);
                } catch (empErr) {
                    console.error("Failed to load employees for anomalies mapping", empErr);
                }

                // Fetch historical anomalies
                const data = await anomalyAPI.getAnomalies();
                setAnomalies(data || []);
                setLoading(false);
            } catch (err) {
                setError(err.detail || 'Failed to load dashboard data.');
                setLoading(false);
            }
        };
        loadInitialData();
    }, []);

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (!window.confirm('Are you sure you want to remove this alert?')) return;
        try {
            await anomalyAPI.deleteAnomaly(id);
            setAnomalies(prev => prev.filter(a => a.id !== id));
            if (selectedAlertForModal && selectedAlertForModal.id === id) {
                setSelectedAlertForModal(null);
            }
        } catch (err) {
            console.error("Failed to delete anomaly", err);
            alert("Failed to delete alert.");
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

    // Filter anomalies based on type, time, and search query
    const filteredAnomalies = anomalies.filter(anom => {
        // Route-level Page Splitting
        if (isRoomAlertsPage) {
            if (anom.anomaly_type !== 'out_of_bounds') return false;
        } else {
            if (anom.anomaly_type === 'out_of_bounds') return false;
        }

        // Type filter (only applicable on security anomalies page)
        if (!isRoomAlertsPage && selectedType !== 'All' && anom.anomaly_type !== selectedType) {
            return false;
        }

        // Time filter
        if (selectedTime !== 'All Time' && anom.detected_at) {
            const anomTime = new Date(anom.detected_at).getTime();
            const now = Date.now();
            if (selectedTime === 'Last 24 Hours' && now - anomTime > 24 * 60 * 60 * 1000) return false;
            if (selectedTime === 'Last 7 Days' && now - anomTime > 7 * 24 * 60 * 60 * 1000) return false;
        }

        // Search Term: matches description, camera, or resolved employee name
        if (searchTerm) {
            const query = searchTerm.toLowerCase();
            const descMatch = (anom.description || '').toLowerCase().includes(query);
            const camMatch = (anom.camera_id || '').toLowerCase().includes(query);
            
            let empMatch = false;
            if (anom.employee_id && employeesMap[anom.employee_id]) {
                const emp = employeesMap[anom.employee_id];
                empMatch = `${emp.first_name} ${emp.last_name}`.toLowerCase().includes(query) ||
                           (emp.role || '').toLowerCase().includes(query);
            }
            
            return descMatch || camMatch || empMatch;
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
        if (!window.confirm(`Are you sure you want to delete ${selectedIds.size} selected alerts?`)) return;

        try {
            await anomalyAPI.bulkDelete(Array.from(selectedIds));
            setAnomalies(prev => prev.filter(a => !selectedIds.has(a.id)));
            setSelectedIds(new Set());
            setIsSelectMode(false);
        } catch (err) {
            console.error("Bulk delete failed", err);
            alert("Failed to delete selected alerts.");
        }
    };

    const handleDeleteAll = async () => {
        if (!window.confirm(`WARNING: Are you sure you want to delete ALL alerts in this view? This cannot be undone.`)) return;

        try {
            const idsToDelete = filteredAnomalies.map(a => a.id);
            if (idsToDelete.length > 0) {
                await anomalyAPI.bulkDelete(idsToDelete);
                setAnomalies(prev => prev.filter(a => !idsToDelete.includes(a.id)));
            }
            setSelectedIds(new Set());
            setIsSelectMode(false);
        } catch (err) {
            console.error("Delete all failed", err);
            alert("Failed to delete alerts.");
        }
    };

    // Calculate unique types for Security page dropdown (exclude out_of_bounds)
    const uniqueTypes = ['All', ...new Set(anomalies
        .filter(a => a.anomaly_type !== 'out_of_bounds')
        .map(a => a.anomaly_type)
        .filter(Boolean)
    )];

    // Stats calculations
    const pageScopeAnomalies = anomalies.filter(a => isRoomAlertsPage ? a.anomaly_type === 'out_of_bounds' : a.anomaly_type !== 'out_of_bounds');
    const totalCount = pageScopeAnomalies.length;
    const highConfidenceCount = pageScopeAnomalies.filter(a => (a.confidence_score || 0) >= 0.8).length;
    const recentCount = pageScopeAnomalies.filter(a => a.detected_at && (Date.now() - new Date(a.detected_at).getTime() < 30 * 60 * 1000)).length;

    // Charts calculations based on filtered anomalies
    const typeDistribution = Object.entries(
        filteredAnomalies.reduce((acc, curr) => {
            const label = isRoomAlertsPage 
                ? (curr.camera_id || 'unknown')
                : (curr.anomaly_type || 'unknown').replace('_', ' ').toUpperCase();
            acc[label] = (acc[label] || 0) + 1;
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

    // Modal helpers
    const closeModal = () => setSelectedAlertForModal(null);

    return (
        <DashboardLayout title={isRoomAlertsPage ? "Room Activity & Attendance Alerts" : "Security Threats & Anomalies"}>
            {/* Live Anomaly Notification Toast */}
            {notification && (
                <div onClick={() => {
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                    setNotification(null);
                }} style={{ cursor: 'pointer' }}>
                    <ToastNotification 
                        type="error"
                        title="Real-Time Incident"
                        subtitle={notification.anomaly_type.replace('_', ' ').toUpperCase()}
                        message={notification.description || 'Unknown event detected. Click to focus.'}
                        onClose={() => setNotification(null)}
                    />
                </div>
            )}
            
            <div className="anomalies-container">
                {/* Stats Grid Widget Row */}
                <div className="alerts-stats-grid">
                    <div className="stat-card total">
                        <div className="stat-icon-wrapper">{isRoomAlertsPage ? '🚪' : '🚨'}</div>
                        <div className="stat-info">
                            <span className="stat-value">{totalCount}</span>
                            <span className="stat-label">{isRoomAlertsPage ? 'Room Violations' : 'Security Incidents'}</span>
                        </div>
                    </div>
                    <div className="stat-card high-confidence">
                        <div className="stat-icon-wrapper">⚠️</div>
                        <div className="stat-info">
                            <span className="stat-value">{highConfidenceCount}</span>
                            <span className="stat-label">Critical Alerts (&gt;80%)</span>
                        </div>
                    </div>
                    <div className="stat-card live-status">
                        <div className="stat-icon-wrapper">
                            <span className="live-indicator-dot"></span>
                        </div>
                        <div className="stat-info">
                            <span className="stat-value">{recentCount}</span>
                            <span className="stat-label">Alerts Last 30m</span>
                        </div>
                    </div>
                </div>

                {/* Visual Analytics Row */}
                {!loading && !error && filteredAnomalies.length > 0 && (
                    <div className="anomalies-analytics-row">
                        <div className="analytics-card">
                            <h3>{isRoomAlertsPage ? "Violations by Camera Location" : "Incidents Classification"}</h3>
                            <div className="chart-container-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie 
                                            data={typeDistribution} 
                                            cx="50%" 
                                            cy="50%" 
                                            innerRadius={60} 
                                            outerRadius={90} 
                                            paddingAngle={4} 
                                            dataKey="value"
                                        >
                                            {typeDistribution.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip 
                                            contentStyle={{ 
                                                background: 'rgba(255, 255, 255, 0.95)',
                                                borderRadius: '12px', 
                                                border: '1px solid rgba(226, 232, 240, 0.8)',
                                                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.05)'
                                            }} 
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="analytics-card animate-chart">
                            <h3>Hourly Chronological Load</h3>
                            <div className="chart-container-wrapper">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={hourlyDistribution}>
                                        <defs>
                                            <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={isRoomAlertsPage ? "#0ea5e9" : "#ef4444"} stopOpacity={0.4}/>
                                                <stop offset="95%" stopColor={isRoomAlertsPage ? "#0ea5e9" : "#ef4444"} stopOpacity={0.0}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
                                        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
                                        <Tooltip 
                                            contentStyle={{ 
                                                background: 'rgba(255, 255, 255, 0.95)',
                                                borderRadius: '12px', 
                                                border: '1px solid rgba(226, 232, 240, 0.8)'
                                            }} 
                                        />
                                        <Area type="monotone" dataKey="count" stroke={isRoomAlertsPage ? "#0ea5e9" : "#ef4444"} strokeWidth={2} fillOpacity={1} fill="url(#colorCount)" name="Alerts" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}

                {/* Filters Row */}
                {!loading && !error && (
                    <div className="anomalies-filters">
                        <div className="filter-left-section">
                            <div className="filter-group">
                                <input
                                    type="text"
                                    placeholder="Search by description, room, employee..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="search-alerts-input"
                                />
                            </div>
                            <div className="filter-group">
                                <label>Time Frame</label>
                                <select value={selectedTime} onChange={(e) => setSelectedTime(e.target.value)}>
                                    <option value="All Time">All Time</option>
                                    <option value="Last 24 Hours">Last 24 Hours</option>
                                    <option value="Last 7 Days">Last 7 Days</option>
                                </select>
                            </div>
                            {!isRoomAlertsPage && (
                                <div className="filter-group">
                                    <label>Incident Type</label>
                                    <select value={selectedType} onChange={(e) => setSelectedType(e.target.value)}>
                                        {uniqueTypes.map(type => (
                                            <option key={type} value={type}>{type.replace('_', ' ').toUpperCase()}</option>
                                        ))}
                                    </select>
                                </div>
                            )}
                        </div>
                        <div className="filter-group button-group-right">
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
                                        Clear Feed
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                )}

                {loading && <div className="alerts-loading">Querying feeds database...</div>}
                {error && <div className="alerts-error">System Error: {error}</div>}
                {!loading && !error && filteredAnomalies.length === 0 && (
                    <div className="anomalies-empty-state">
                        <div className="empty-state-icon">🔔</div>
                        <h3>No events logged</h3>
                        <p>No records match active filters.</p>
                    </div>
                )}
                
                <div className="anomalies-grid">
                    {filteredAnomalies.map((item) => {
                        const associatedEmployee = item.employee_id ? employeesMap[item.employee_id] : null;
                        const isRecentlyDetected = item.detected_at && (Date.now() - new Date(item.detected_at).getTime() < 10 * 60 * 1000);
                        
                        return (
                            <div 
                                key={item.id} 
                                className={`anomaly-card ${isSelectMode && selectedIds.has(item.id) ? 'selected' : ''} ${isRecentlyDetected ? 'recent-active' : ''}`}
                                onClick={() => {
                                    if (isSelectMode) {
                                        toggleSelection(item.id);
                                    } else {
                                        setSelectedAlertForModal(item);
                                    }
                                }}
                                style={{ cursor: 'pointer', outline: isSelectMode && selectedIds.has(item.id) ? '3px solid #3b82f6' : 'none' }}
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
                                        title="Remove this alert"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                    </button>
                                )}

                                <div className="anomaly-image-wrapper">
                                    <img
                                        src={item.image_url || (associatedEmployee && associatedEmployee.profile_image_url) || '/assets/images/camera.png'}
                                        alt={item.anomaly_type}
                                        className="anomaly-image"
                                        onError={(e) => { e.target.src = '/assets/images/camera.png'; }}
                                    />
                                    <div className="card-top-indicators">
                                        <span className="camera-id-badge">📹 {item.camera_id}</span>
                                        {isRecentlyDetected && <span className="live-pill">LIVE</span>}
                                    </div>
                                </div>
                                <div className="anomaly-content">
                                    <div className="anomaly-header-row">
                                        <span className="anomaly-type-badge" style={{ background: BADGE_COLORS[item.anomaly_type] || '#6b7280' }}>
                                            {TYPE_EMOJIS[item.anomaly_type] || '❓'} {item.anomaly_type.replace('_', ' ')}
                                        </span>
                                        <span className={`confidence-badge ${item.confidence_score >= 0.8 ? 'high' : 'medium'}`}>
                                            {(item.confidence_score * 100).toFixed(0)}% Match
                                        </span>
                                    </div>
                                    
                                    <h3 className="anomaly-title">
                                        {item.description || 'No description available.'}
                                    </h3>

                                    {/* Confidence Bar Meter */}
                                    <div className="confidence-meter-container">
                                        <div className="confidence-meter-label">AI Confidence Index</div>
                                        <div className="confidence-meter-bar-bg">
                                            <div 
                                                className={`confidence-meter-bar-fill ${item.confidence_score >= 0.8 ? 'high' : 'medium'}`} 
                                                style={{ width: `${(item.confidence_score * 100).toFixed(0)}%` }}
                                            ></div>
                                        </div>
                                    </div>

                                    {/* Resolved Employee Profiler Card */}
                                    {associatedEmployee ? (
                                        <div className="resolved-employee-card">
                                            <EmployeeAvatar 
                                                imageUrl={associatedEmployee.profile_image_url}
                                                firstName={associatedEmployee.first_name}
                                                lastName={associatedEmployee.last_name}
                                                size={32}
                                            />
                                            <div className="emp-details">
                                                <div className="emp-name">{associatedEmployee.first_name} {associatedEmployee.last_name}</div>
                                                <div className="emp-role">{associatedEmployee.role}</div>
                                            </div>
                                        </div>
                                    ) : item.employee_id ? (
                                        <div className="resolved-employee-card unrecognized">
                                            <div className="unrecognized-avatar">👤</div>
                                            <div className="emp-details">
                                                <div className="emp-name">ID: {item.employee_id.substring(0, 8)}...</div>
                                                <div className="emp-role">Unresolved Track ID</div>
                                            </div>
                                        </div>
                                    ) : null}

                                    <div className="anomaly-footer">
                                        <span className="anomaly-timestamp">🕰️ {item.detected_at ? timeAgo(item.detected_at) : ''}</span>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Issue-Specific Details Modal */}
            {selectedAlertForModal && (
                <div className="modal-overlay" onClick={closeModal}>
                    <div className="alert-detail-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>Alert Details</h3>
                            <button className="close-btn" onClick={closeModal}>×</button>
                        </div>
                        
                        <div className="modal-body">
                            {selectedAlertForModal.anomaly_type === 'out_of_bounds' ? (
                                /* Issue Type: Room Activity / Attendance Violations */
                                <div className="room-alert-detail">
                                    <div className="modal-alert-type-header out-of-bounds">
                                        <span className="icon">🚪</span>
                                        <div className="title-block">
                                            <h4>Routine Boundary Violation</h4>
                                            <p>Detected at Room {selectedAlertForModal.camera_id}</p>
                                        </div>
                                    </div>

                                    <div className="modal-section-title">Associated Employee</div>
                                    {selectedAlertForModal.employee_id && employeesMap[selectedAlertForModal.employee_id] ? (
                                        (() => {
                                            const emp = employeesMap[selectedAlertForModal.employee_id];
                                            return (
                                                <div className="modal-employee-card">
                                                    <EmployeeAvatar 
                                                        imageUrl={emp.profile_image_url}
                                                        firstName={emp.first_name}
                                                        lastName={emp.last_name}
                                                        size={60}
                                                    />
                                                    <div className="emp-meta">
                                                        <h5>{emp.first_name} {emp.last_name}</h5>
                                                        <span className="badge">{emp.role}</span>
                                                        <p className="shift-hours">⏰ Shift: {emp.assigned_shift_start || 'N/A'} - {emp.assigned_shift_end || 'N/A'}</p>
                                                    </div>
                                                </div>
                                            );
                                        })()
                                    ) : (
                                        <div className="modal-employee-card unrecognized">
                                            <div className="avatar-dummy">👤</div>
                                            <div className="emp-meta">
                                                <h5>Unresolved Employee Track</h5>
                                                <p>Track ID: {selectedAlertForModal.employee_id || 'Unknown'}</p>
                                            </div>
                                        </div>
                                    )}

                                    <div className="modal-section-title">Schedule & Routine Conflict</div>
                                    {selectedAlertForModal.employee_id && employeesMap[selectedAlertForModal.employee_id] ? (
                                        (() => {
                                            const emp = employeesMap[selectedAlertForModal.employee_id];
                                            return (
                                                <div className="schedule-detail-box">
                                                    <div className="detail-item">
                                                        <strong>Routine Days:</strong>
                                                        <div className="days-indicator-row" style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                                                            {WEEKDAYS_FULL.map((d, index) => {
                                                                const isActive = (emp.assigned_days || []).includes(index);
                                                                return (
                                                                    <span 
                                                                        key={d} 
                                                                        style={{
                                                                            fontSize: '11px',
                                                                            padding: '3px 8px',
                                                                            borderRadius: '20px',
                                                                            background: isActive ? '#0284c7' : '#334155',
                                                                            color: isActive ? '#ffffff' : '#94a3b8',
                                                                            fontWeight: isActive ? 'bold' : 'normal'
                                                                        }}
                                                                    >
                                                                        {d.substring(0, 3)}
                                                                    </span>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                    <div className="detail-item" style={{ marginTop: '12px' }}>
                                                        <strong>Camera IDs Boundaries:</strong>
                                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                                                            {(emp.assigned_camera_ids || []).map(id => (
                                                                <span key={id} style={{ fontSize: '11px', padding: '2px 8px', background: '#1e293b', border: '1px solid #475569', borderRadius: '4px', color: '#e2e8f0' }}>
                                                                    📹 {id}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })()
                                    ) : (
                                        <p style={{ fontSize: '13px', color: '#94a3b8' }}>Could not resolve scheduling parameters since employee identity track is unrecognized.</p>
                                    )}

                                    <div className="modal-section-title" style={{ marginTop: '16px' }}>Violation Description</div>
                                    <div className="description-speech-bubble">
                                        "{selectedAlertForModal.description}"
                                    </div>
                                    
                                    <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
                                        <button className="btn-secondary" style={{ flex: 1 }} onClick={closeModal}>Dismiss View</button>
                                        <button className="btn-danger" style={{ flex: 1 }} onClick={(e) => handleDelete(selectedAlertForModal.id, e)}>Erase Incident Log</button>
                                    </div>
                                </div>
                            ) : (
                                /* Issue Type: Security Threats (Violence, Theft, Vandalism, Unusual behavior) */
                                <div className="security-alert-detail">
                                    <div className="modal-alert-type-header security">
                                        <span className="icon">{TYPE_EMOJIS[selectedAlertForModal.anomaly_type] || '🚨'}</span>
                                        <div className="title-block">
                                            <h4>Security Threat: {selectedAlertForModal.anomaly_type.replace('_', ' ').toUpperCase()}</h4>
                                            <p>Source Feed: Camera {selectedAlertForModal.camera_id}</p>
                                        </div>
                                    </div>

                                    <div className="modal-image-showcase">
                                        <img 
                                            src={selectedAlertForModal.image_url || (selectedAlertForModal.employee_id && employeesMap[selectedAlertForModal.employee_id]?.profile_image_url) || '/assets/images/camera.png'} 
                                            alt="Security Event Capture"
                                            onError={(e) => { e.target.src = '/assets/images/camera.png'; }}
                                        />
                                        <span className="badge-confidence">AI Match: {(selectedAlertForModal.confidence_score * 100).toFixed(1)}%</span>
                                    </div>

                                    <div className="modal-section-title">Threat Assessment</div>
                                    <div className="description-speech-bubble security-theme">
                                        "{selectedAlertForModal.description}"
                                    </div>

                                    <div className="modal-section-title" style={{ marginTop: '16px' }}>Incident Information</div>
                                    <div className="incident-meta-list">
                                        <div className="meta-item">
                                            <span>Detected At</span>
                                            <strong>{new Date(selectedAlertForModal.detected_at).toLocaleString()}</strong>
                                        </div>
                                        <div className="meta-item">
                                            <span>Threat Confidence Index</span>
                                            <strong style={{ color: selectedAlertForModal.confidence_score >= 0.8 ? '#ef4444' : '#eab308' }}>
                                                {selectedAlertForModal.confidence_score >= 0.8 ? 'CRITICAL RISK' : 'MEDIUM RISK'} ({(selectedAlertForModal.confidence_score * 100).toFixed(0)}%)
                                            </strong>
                                        </div>
                                    </div>

                                    <div className="threat-controls-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '24px' }}>
                                        <button className="btn-secondary" onClick={closeModal}>Close Details</button>
                                        <button 
                                            className="btn-danger" 
                                            onClick={() => {
                                                alert("Incident flagged. Security personnel dispatched.");
                                                closeModal();
                                            }}
                                        >
                                            ⚡ Dispatch Security
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default Anomalies;
