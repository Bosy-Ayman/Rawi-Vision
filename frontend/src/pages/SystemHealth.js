import React from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';

const SystemHealth = () => {
    return (
        <DashboardLayout title="System Health Overview">
            <div className="system-health-container" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', height: 'calc(100vh - 200px)' }}>
                <div className="header-section" style={{ marginBottom: '0' }}>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#ffffff', margin: 0 }}>System Health Dashboard</h1>
                    <p style={{ color: '#a0aec0', marginTop: '0.5rem' }}>Real-time observability and metrics for the Rawi Vision Platform.</p>
                </div>

                <div className="iframe-container" style={{ flex: 1, borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <iframe
                        src="http://localhost:3001/d/system_health/system-health-overview?orgId=1&refresh=5s"
                        width="100%"
                        height="100%"
                        frameBorder="0"
                        title="Grafana Dashboard"
                        style={{ background: '#1a202c' }}
                    ></iframe>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default SystemHealth;
