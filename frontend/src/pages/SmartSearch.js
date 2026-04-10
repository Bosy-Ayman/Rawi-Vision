import React from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';

const SmartSearch = () => {
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
                    <div className="search-input-wrapper">
                        <div className="search-icon-placeholder">
                            <img src="/assets/icons/search-icon.svg" alt="Search" style={{ width: '24px', height: '24px', opacity: 0.5 }} />
                        </div>
                        <input
                            type="text"
                            className="smart-search-input"
                            placeholder="Search by context or description... e.g. 'Find video clips where two people are fighting near the reception desk'"
                        />
                        <button className="enter-btn">Enter</button>
                    </div>
                </div>

            </div>
        </DashboardLayout>
    );
};

export default SmartSearch;
