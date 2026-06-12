import React from 'react';
import { useSubscription } from '../../context/SubscriptionContext';

const SubscriptionGuard = ({ children }) => {
    const { status, isLoading, installationUuid } = useSubscription();

    if (isLoading) {
        return (
            <div style={styles.loadingContainer}>
                <div style={styles.spinner}></div>
                <p style={styles.loadingText}>Checking License Status...</p>
            </div>
        );
    }

    const isBlocked = status === 'suspended' || status === 'expired' || status === 'canceled';

    if (isBlocked) {
        return (
            <div style={styles.blockedOverlay}>
                <div style={styles.glassCard}>
                    <div style={styles.iconContainer}>
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#ff4757" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                        </svg>
                    </div>
                    <h1 style={styles.title}>Subscription Suspended</h1>
                    <p style={styles.message}>
                        The license key for this installation is currently <strong>{status}</strong>. 
                        Please renew or reactivate your subscription package to restore access.
                    </p>
                    
                    <div style={styles.detailsBox}>
                        <div style={styles.detailRow}>
                            <span style={styles.detailLabel}>Installation ID:</span>
                            <span style={styles.detailValue}>{installationUuid}</span>
                        </div>
                        <div style={styles.detailRow}>
                            <span style={styles.detailLabel}>Status:</span>
                            <span style={{ ...styles.detailValue, color: '#ff4757', fontWeight: 'bold' }}>{status.toUpperCase()}</span>
                        </div>
                    </div>

                    <a 
                        href={`http://localhost:8001/payment/checkout/${installationUuid}`} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        style={styles.actionButton}
                    >
                        Renew Subscription
                    </a>
                </div>
            </div>
        );
    }

    return children;
};

const styles = {
    loadingContainer: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: '#0a0b10',
    },
    spinner: {
        width: '50px',
        height: '50px',
        border: '3px solid rgba(255,255,255,0.1)',
        borderTop: '3px solid #6c5ce7',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
    },
    loadingText: {
        color: '#a0a0b0',
        marginTop: '20px',
        fontFamily: "'Inter', sans-serif",
    },
    blockedOverlay: {
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        backgroundColor: 'rgba(10, 11, 16, 0.95)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 999999,
        backdropFilter: 'blur(10px)',
        fontFamily: "'Inter', sans-serif",
    },
    glassCard: {
        width: '90%',
        maxWidth: '500px',
        padding: '40px',
        borderRadius: '24px',
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.3)',
        textAlign: 'center',
    },
    iconContainer: {
        marginBottom: '24px',
        display: 'inline-block',
        padding: '16px',
        borderRadius: '50%',
        background: 'rgba(255, 71, 87, 0.1)',
    },
    title: {
        fontSize: '28px',
        fontWeight: '700',
        color: '#ffffff',
        margin: '0 0 16px 0',
    },
    message: {
        fontSize: '15px',
        color: '#b0b3c6',
        lineHeight: '1.6',
        margin: '0 0 24px 0',
    },
    detailsBox: {
        background: 'rgba(0, 0, 0, 0.2)',
        borderRadius: '12px',
        padding: '16px',
        marginBottom: '32px',
        textAlign: 'left',
    },
    detailRow: {
        display: 'flex',
        justifyContent: 'space-between',
        marginBottom: '8px',
        fontSize: '13px',
    },
    detailLabel: {
        color: '#707593',
    },
    detailValue: {
        color: '#ffffff',
        fontFamily: 'monospace',
    },
    actionButton: {
        display: 'block',
        width: '100%',
        padding: '14px',
        borderRadius: '12px',
        background: 'linear-gradient(135deg, #6c5ce7, #a29bfe)',
        color: '#ffffff',
        textDecoration: 'none',
        fontWeight: '600',
        fontSize: '16px',
        transition: 'transform 0.2s',
        border: 'none',
        cursor: 'pointer',
    }
};

// Add standard keyframe spin styles for the loading state dynamically
if (typeof document !== 'undefined') {
    const styleSheet = document.createElement("style");
    styleSheet.type = "text/css";
    styleSheet.innerText = `
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(styleSheet);
}

export default SubscriptionGuard;
