import React from 'react';

const ToastNotification = ({ type = 'success', title, subtitle, message, onClose }) => {
    const isError = type === 'error';
    const bgColor = isError ? '#fff1f2' : '#f0fdf4';
    const borderColor = isError ? '#ef4444' : '#22c55e';
    const titleColor = isError ? '#be123c' : '#166534';
    const icon = isError ? '🚨' : '✅';

    return (
        <div style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            backgroundColor: bgColor,
            borderLeft: `4px solid ${borderColor}`,
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            padding: '16px',
            borderRadius: '8px',
            zIndex: 9999,
            width: '320px',
            animation: 'slideIn 0.3s ease-out',
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ color: titleColor, fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '20px' }}>{icon}</span> {title}
                </strong>
                <button
                    onClick={onClose}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px', color: '#9ca3af' }}
                >
                    ✕
                </button>
            </div>
            <div style={{ marginTop: '12px' }}>
                {subtitle && (
                    <p style={{ color: '#111827', fontWeight: '600', textTransform: 'uppercase', fontSize: '14px', margin: 0 }}>
                        {subtitle}
                    </p>
                )}
                <p style={{ color: '#4b5563', fontSize: '13px', margin: subtitle ? '4px 0 0 0' : '0' }}>
                    {message}
                </p>
            </div>
        </div>
    );
};

export default ToastNotification;
