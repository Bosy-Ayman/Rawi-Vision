import React from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { authAPI } from '../../api/auth';

import { useSubscription } from '../../context/SubscriptionContext';

const Sidebar = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const { capabilities } = useSubscription();

    const handleLogout = async (e) => {
        e.preventDefault();
        try {
            await authAPI.logout();
        } catch (err) {
            console.error('Logout failed:', err);
        }
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_role');
        localStorage.removeItem('full_name');
        navigate('/');
    };

    // HR Journey: employee management pages
    const isHRJourney =
        location.pathname === '/dashboard/employee-onboarding' ||
        location.pathname === '/dashboard/all-employees' ||
        location.pathname.startsWith('/dashboard/employee/') ||
        location.pathname === '/dashboard/camera-onboarding' ||
        location.pathname === '/dashboard/all-cameras';

    // SuperAdmin Journey: system user management
    const isSuperAdminJourney = location.pathname === '/admin/system-users';

    const standardMenuItems = [
        { name: 'Video Feed', icon: 'video-feed.svg', path: '/dashboard/video-feed' },
        { name: 'Smart Search', icon: 'smart-search.svg', path: '/dashboard/smart-search', requiredCapability: 'search' },
        { name: 'Security Alerts', icon: 'anomalies.svg', path: '/dashboard/anomalies' },
        { name: 'Room Alerts', icon: 'anomalies.svg', path: '/dashboard/room-alerts' },
        { name: 'Dashboard', icon: 'dashboard.svg', path: '/dashboard/main' },
        { name: 'Clips', icon: 'employee-insights.svg', path: '/dashboard/clips' },
        { name: 'Employee insights', icon: 'employee-insights.svg', path: '/dashboard/employee-insights', requiredCapability: 'summarization' },
        { name: 'Settings', icon: 'settings.svg', path: '/dashboard/settings' }
    ];

    const hrMenuItems = [
        { name: 'Add Employee', icon: 'employee-insights.svg', path: '/dashboard/employee-onboarding' },
        { name: 'All Employees', icon: 'employee-insights.svg', path: '/dashboard/all-employees' },
        { name: 'Add Camera', icon: 'employee-insights.svg', path: '/dashboard/camera-onboarding' },
        { name: 'All Cameras', icon: 'employee-insights.svg', path: '/dashboard/all-cameras' }
    ];

    const superAdminMenuItems = [
        { name: 'Add Users', icon: 'employee-insights.svg', path: '/admin/system-users' }
    ];

    const menuItems = isSuperAdminJourney ? superAdminMenuItems : isHRJourney ? hrMenuItems : standardMenuItems;

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <img src="/assets/images/logo.svg" alt="Rawi Vision" />
            </div>

            <nav className="sidebar-nav">
                <ul>
                    {menuItems.map((item) => {
                        const isLocked = item.requiredCapability && !capabilities[item.requiredCapability];
                        return (
                            <li key={item.name}>
                                <NavLink
                                    to={isLocked ? '#' : item.path}
                                    onClick={(e) => {
                                        if (isLocked) {
                                            e.preventDefault();
                                            alert(`The '${item.name}' feature is locked. Please upgrade your subscription plan.`);
                                        }
                                    }}
                                    className={({ isActive }) => `sidebar-link ${isActive && !isLocked ? 'active' : ''}`}
                                    style={isLocked ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
                                >
                                    <img
                                        src={`/assets/icons/sidebar/${item.icon}`}
                                        alt={item.name}
                                        className="sidebar-icon"
                                    />
                                    <span className="sidebar-text">{item.name}</span>
                                    {isLocked && (
                                        <span className="sidebar-upgrade-badge">Upgrade</span>
                                    )}
                                </NavLink>
                            </li>
                        );
                    })}
                </ul>
            </nav>

            <div className="sidebar-footer">
                <a href="/" onClick={handleLogout} className="sidebar-link sign-out">
                    <img
                        src="/assets/icons/sidebar/sign-out.svg"
                        alt="Sign Out"
                        className="sidebar-icon"
                    />
                    <span className="sidebar-text">Sign Out</span>
                </a>
            </div>
        </aside>
    );
};

export default Sidebar;
