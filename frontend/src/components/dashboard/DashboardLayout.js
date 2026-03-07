import React from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

const DashboardLayout = ({ children, title = "Dashboard" }) => {
    return (
        <div className="dashboard-layout">
            <Sidebar />
            <div className="dashboard-main">
                <TopBar title={title} />
                <div className="dashboard-content">
                    {children}
                </div>
            </div>
        </div>
    );
};

export default DashboardLayout;
