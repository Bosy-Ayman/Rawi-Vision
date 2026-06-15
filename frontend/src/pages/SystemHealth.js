import React from 'react';
import './SystemHealth.css'; // Optional custom styles if needed

const SystemHealth = () => {
    return (
        <div className="system-health-container" style={{ padding: '2rem', height: '100vh', display: 'flex', flexDirection: 'column' }}>
            <div className="header-section" style={{ marginBottom: '1.5rem' }}>
                <h1 style={{ fontSize: '2rem', fontWeight: 'bold', color: '#333' }}>System Health Overview</h1>
                <p style={{ color: '#666' }}>Real-time observability and metrics for the Rawi Vision Platform.</p>
            </div>
            
            <div className="iframe-container" style={{ flex: 1, borderRadius: '8px', overflow: 'hidden', border: '1px solid #ddd' }}>
                <iframe 
                    src="http://localhost:3001/d/system_health/system-health-overview?orgId=1&kiosk" 
                    width="100%" 
                    height="100%" 
                    frameBorder="0"
                    title="Grafana Dashboard"
                    style={{ background: '#f5f5f5' }}
                ></iframe>
            </div>
        </div>
    );
};

export default SystemHealth;
