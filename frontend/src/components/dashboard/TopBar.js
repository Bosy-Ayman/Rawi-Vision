import React from 'react';

const TopBar = ({ title }) => {
    return (
        <header className="topbar">
            <h1 className="page-title">{title}</h1>

            <div className="topbar-actions">
                <div className="language-selector">
                    🇺🇸 Eng (US) ⌄
                </div>

                <button className="notification-btn">
                    🔔
                </button>

                <div className="user-profile">
                    <img
                        src="https://upload.wikimedia.org/wikipedia/commons/7/7c/Profile_avatar_placeholder_large.png"
                        alt="User"
                        className="user-avatar"
                    />
                    <div className="user-info">
                        <span className="user-name">Mustiq</span>
                        <span className="user-role">Admin</span>
                    </div>
                    <span className="dropdown-arrow">⌄</span>
                </div>
            </div>
        </header>
    );
};

export default TopBar;
