import React, { useState } from 'react';
import './EmployeeAvatar.css';

const EmployeeAvatar = ({ imageUrl, firstName, lastName, size = 40 }) => {
    const [imageError, setImageError] = useState(false);

    const fName = firstName || '?';
    const lName = lastName || '?';
    const initials = `${fName.charAt(0)}${lName.charAt(0)}`.toUpperCase();

    const style = {
        width: `${size}px`,
        height: `${size}px`,
        fontSize: `${Math.max(12, size * 0.35)}px`
    };

    if (imageUrl && !imageError) {
        return (
            <img 
                src={imageUrl} 
                alt={`${fName} ${lName}`} 
                className="employee-avatar-img"
                style={style}
                onError={() => setImageError(true)}
            />
        );
    }

    return (
        <div className="employee-avatar-placeholder" style={style}>
            {initials}
        </div>
    );
};

export default EmployeeAvatar;
