import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { anomalyAPI } from '../../api/anomalies';

const BADGE_COLORS = {
    violence: '#ef4444',
    theft: '#f97316',
    vandalism: '#f59e0b',
    unusual_behavior: '#8b5cf6',
    out_of_bounds: '#0ea5e9',
    unknown: '#6b7280',
};

const TYPE_EMOJIS = {
    violence: '⚠️',
    theft: '🚨',
    vandalism: '🛠️',
    unusual_behavior: '👁️',
    out_of_bounds: '🚪',
    unknown: '❓'
};

const TopBar = ({ title }) => {
    const [anomalies, setAnomalies] = useState([]);
    const [showDropdown, setShowDropdown] = useState(false);
    const navigate = useNavigate();

    const fetchAlerts = async () => {
        try {
            const data = await anomalyAPI.getAnomalies();
            setAnomalies(data || []);
        } catch (err) {
            console.error("TopBar failed to fetch notification alerts", err);
        }
    };

    useEffect(() => {
        fetchAlerts();
        const intv = setInterval(fetchAlerts, 5000);
        return () => clearInterval(intv);
    }, []);

    const dismissAlert = async (id, e) => {
        e.stopPropagation();
        try {
            await anomalyAPI.deleteAnomaly(id);
            setAnomalies(prev => prev.filter(a => a.id !== id));
        } catch (err) {
            console.error("Failed to dismiss alert", err);
        }
    };

    return (
        <header className="topbar">
            <h1 className="page-title">{title}</h1>

            <div className="topbar-actions">
                {/* <div className="language-selector">
                    🇺🇸 Eng (US) ⌄
                </div> */}

                <div className="notification-container" style={{ position: 'relative' }}>
                    <button 
                        className="notification-btn" 
                        onClick={() => setShowDropdown(!showDropdown)}
                        onDoubleClick={() => navigate('/dashboard/anomalies')}
                        title="Double-click to view historical alerts list"
                        style={{ cursor: 'pointer', position: 'relative' }}
                    >
                        🔔
                        {anomalies.length > 0 && (
                            <span className="notification-badge" style={{
                                position: 'absolute',
                                top: '-4px',
                                right: '-4px',
                                backgroundColor: '#ef4444',
                                color: 'white',
                                borderRadius: '50%',
                                padding: '2px 6px',
                                fontSize: '10px',
                                fontWeight: 'bold'
                            }}>
                                {anomalies.length}
                            </span>
                        )}
                    </button>

                    {showDropdown && (
                        <div className="notification-dropdown" style={{
                            position: 'absolute',
                            top: '45px',
                            right: '0',
                            width: '360px',
                            background: '#ffffff',
                            border: '1px solid #e2e8f0',
                            borderRadius: '12px',
                            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
                            zIndex: 1000,
                            padding: '16px',
                            fontFamily: 'Inter, sans-serif'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' }}>
                                <h4 style={{ margin: 0, color: '#0f172a', fontSize: '15px', fontWeight: '700' }}>
                                    Recent Notifications
                                </h4>
                                {anomalies.length > 0 && (
                                    <button 
                                        onClick={async () => {
                                            if (window.confirm("Clear all notification logs?")) {
                                                await anomalyAPI.deleteAll();
                                                setAnomalies([]);
                                            }
                                        }}
                                        style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '11px', cursor: 'pointer' }}
                                    >
                                        Clear All
                                    </button>
                                )}
                            </div>
                            
                            <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                                {anomalies.length === 0 ? (
                                    <p style={{ color: '#64748b', fontSize: '13px', margin: '16px 0', textAlign: 'center' }}>No recent alerts.</p>
                                ) : (
                                    anomalies.map(alert => (
                                        <div key={alert.id} style={{
                                            padding: '12px 8px',
                                            borderBottom: '1px solid #f1f5f9',
                                            fontSize: '13px',
                                            color: '#334155',
                                            position: 'relative',
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'flex-start',
                                            gap: '8px',
                                            transition: 'background-color 0.2s',
                                        }} className="notification-item">
                                            <div style={{ flex: 1 }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                                    <span style={{ fontSize: '11px', color: '#ffffff', background: BADGE_COLORS[alert.anomaly_type] || '#6b7280', padding: '2px 8px', borderRadius: '12px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                                        {TYPE_EMOJIS[alert.anomaly_type] || '❓'} {alert.anomaly_type.replace('_', ' ')}
                                                    </span>
                                                    <span style={{ color: '#94a3b8', fontSize: '11px', fontWeight: '500' }}>
                                                        {new Date(alert.detected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                    </span>
                                                </div>
                                                <div style={{ color: '#475569', lineHeight: '1.5' }}>
                                                    {alert.description}
                                                </div>
                                            </div>
                                            <button 
                                                onClick={(e) => dismissAlert(alert.id, e)}
                                                style={{
                                                    background: 'none',
                                                    border: 'none',
                                                    color: '#94a3b8',
                                                    fontSize: '16px',
                                                    cursor: 'pointer',
                                                    padding: '0 4px',
                                                    lineHeight: 1,
                                                    transition: 'color 0.2s'
                                                }}
                                                title="Dismiss notification"
                                                onMouseOver={(e) => e.target.style.color = '#ef4444'}
                                                onMouseOut={(e) => e.target.style.color = '#94a3b8'}
                                            >
                                                ×
                                            </button>
                                        </div>
                                    ))
                                )}
                            </div>

                            <div style={{ textAlign: 'center', marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #f1f5f9' }}>
                                <button 
                                    onClick={() => { navigate('/dashboard/anomalies'); setShowDropdown(false); }}
                                    style={{ background: 'none', border: 'none', color: '#3b82f6', fontSize: '13px', cursor: 'pointer', fontWeight: '600', transition: 'color 0.2s' }}
                                    onMouseOver={(e) => e.target.style.color = '#2563eb'}
                                    onMouseOut={(e) => e.target.style.color = '#3b82f6'}
                                >
                                    View All Alerts History →
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                <div className="user-profile">
                    <img
                        src="https://upload.wikimedia.org/wikipedia/commons/7/7c/Profile_avatar_placeholder_large.png"
                        alt="User"
                        className="user-avatar"
                    />
                    <div className="user-info">
                        <span className="user-name">TestUser</span>
                        <span className="user-role">Admin</span>
                    </div>
                    <span className="dropdown-arrow">⌄</span>
                </div>
            </div>
        </header>
    );
};

export default TopBar;
