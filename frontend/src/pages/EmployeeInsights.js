import React from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';

const EmployeeInsights = () => {
    // Mock data matching the user's screenshot
    const insights = Array(9).fill({
        title: 'Employee 1(Elkady)',
        description: 'He is just great always on time and really a great and smart devloper'
    });

    return (
        <DashboardLayout title="Employee insights">
            <div className="insights-container">
                <div className="insights-grid">
                    {insights.map((item, index) => (
                        <div key={index} className="insight-card">
                            <div className="insight-image-placeholder">
                                {/* SVG for the 'X' placeholder look */}
                                <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
                                    <line x1="0" y1="0" x2="100" y2="100" stroke="#d1d5db" strokeWidth="1" />
                                    <line x1="0" y1="100" x2="100" y2="0" stroke="#d1d5db" strokeWidth="1" />
                                </svg>
                            </div>
                            <div className="insight-content">
                                <h3 className="insight-title">{item.title}</h3>
                                <p className="insight-description">{item.description}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default EmployeeInsights;
