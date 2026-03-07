import React from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';

const Anomalies = () => {
    // Mock data to match the user's image structure
    const anomalies = Array(8).fill({
        title: 'Anamoly One',
        description: 'Someone enjoyed going to university !!!!!',
        time: '2 hours 40 minutes',
        image: '/assets/images/camera.png' // Using existing asset as placeholder
    });

    return (
        <DashboardLayout title="Anomalies">
            <div className="anomalies-container">
                <div className="anomalies-grid">
                    {anomalies.map((item, index) => (
                        <div key={index} className="anomaly-card">
                            <div className="anomaly-image-wrapper">
                                <img src={item.image} alt={item.title} className="anomaly-image" />
                            </div>
                            <div className="anomaly-content">
                                <h3 className="anomaly-title">{item.title}</h3>
                                <p className="anomaly-description">{item.description}</p>
                                <p className="anomaly-time">{item.time}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default Anomalies;
