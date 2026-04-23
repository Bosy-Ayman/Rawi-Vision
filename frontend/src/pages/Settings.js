import React from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';

const Settings = () => {
    return (
        <DashboardLayout title="System Settings">
            <div style={{ 
                display: 'flex', 
                justifyContent: 'center', 
                alignItems: 'center', 
                minHeight: '60vh',
                color: '#7f8c8d',
                fontSize: '1.2rem',
                fontWeight: '400',
                letterSpacing: '0.5px'
            }}>
                <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '3rem', marginBottom: '20px', opacity: 0.5 }}>⚙️</div>
                    <p>will be system settings</p>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default Settings;
