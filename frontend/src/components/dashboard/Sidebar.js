import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const Sidebar = () => {
    const location = useLocation();

    // Admin Journey includes: Add Employee, All Employees (List), and Single Employee Details
    const isSuperAdminJourney =
        location.pathname === '/dashboard/employee-onboarding' ||
        location.pathname === '/dashboard/all-employees' ||
        location.pathname.startsWith('/dashboard/employee/');

    const standardMenuItems = [
        { name: 'Video Feed', icon: 'video-feed.svg', path: '/dashboard/video-feed' },
        { name: 'Smart Search', icon: 'smart-search.svg', path: '/dashboard/smart-search' },
        { name: 'Anomalies', icon: 'anomalies.svg', path: '/dashboard/anomalies' },
        { name: 'Dashboard', icon: 'dashboard.svg', path: '/dashboard/main' },
        { name: 'Employee insights', icon: 'employee-insights.svg', path: '/dashboard/employee-insights' },
        { name: 'Settings', icon: 'settings.svg', path: '/dashboard/settings' }
    ];

    const superAdminMenuItems = [
        { name: 'Add Employee', icon: 'employee-insights.svg', path: '/dashboard/employee-onboarding' },
        { name: 'All Employees', icon: 'employee-insights.svg', path: '/dashboard/all-employees' },
        { name: 'Back to Feed', icon: 'video-feed.svg', path: '/dashboard/video-feed' }
    ];

    const menuItems = isSuperAdminJourney ? superAdminMenuItems : standardMenuItems;

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <img src="/assets/images/logo.svg" alt="Rawi Vision" />
            </div>

            <nav className="sidebar-nav">
                <ul>
                    {menuItems.map((item) => (
                        <li key={item.name}>
                            <NavLink
                                to={item.path}
                                className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
                            >
                                <img
                                    src={`/assets/icons/sidebar/${item.icon}`}
                                    alt={item.name}
                                    className="sidebar-icon"
                                />
                                <span className="sidebar-text">{item.name}</span>
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </nav>

            <div className="sidebar-footer">
                <NavLink to="/" className="sidebar-link sign-out">
                    <img
                        src="/assets/icons/sidebar/sign-out.svg"
                        alt="Sign Out"
                        className="sidebar-icon"
                    />
                    <span className="sidebar-text">Sign Out</span>
                </NavLink>
            </div>
        </aside>
    );
};

export default Sidebar;
