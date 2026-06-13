import React, { useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { useSubscription } from '../context/SubscriptionContext';

const Settings = () => {
    const { status, capabilities, installationUuid, checkSubscriptionStatus } = useSubscription();
    const [keyInput, setKeyInput] = useState(installationUuid);
    const [successMessage, setSuccessMessage] = useState('');

    const handleSaveKey = async (e) => {
        e.preventDefault();
        localStorage.setItem('installation_uuid', keyInput.trim());
        await checkSubscriptionStatus();
        setSuccessMessage('License Key updated and verified successfully!');
        setTimeout(() => setSuccessMessage(''), 4000);
    };

    return (
        <DashboardLayout title="System Settings">
            <div style={styles.container}>
                <div style={styles.grid}>
                    {/* License Information Card */}
                    <div style={styles.card}>
                        <h2 style={styles.cardTitle}>License & Activation</h2>
                        <p style={styles.cardDescription}>
                            Manage your local client installation credentials and view real-time billing state.
                        </p>

                        <form onSubmit={handleSaveKey} style={styles.form}>
                            <div style={styles.inputGroup}>
                                <label style={styles.label}>Installation License UUID</label>
                                <input 
                                    type="text" 
                                    value={keyInput} 
                                    onChange={(e) => setKeyInput(e.target.value)} 
                                    style={styles.input} 
                                    placeholder="Enter your subscription Installation ID"
                                    required
                                />
                            </div>

                            <button type="submit" style={styles.button}>
                                Update License Key
                            </button>
                        </form>

                        {successMessage && (
                            <div style={styles.successAlert}>
                                {successMessage}
                            </div>
                        )}

                        <div style={styles.statusBox}>
                            <div style={styles.statusRow}>
                                <span style={styles.statusLabel}>Server Status:</span>
                                <span style={{ 
                                    ...styles.statusValue, 
                                    color: status === 'active' || status === 'ok' ? '#2ecc71' : '#e74c3c' 
                                }}>
                                    {status.toUpperCase()}
                                </span>
                            </div>
                            <div style={styles.statusRow}>
                                <span style={styles.statusLabel}>Billing Provider Link:</span>
                                <a 
                                    href="http://localhost:8001/subscriptions" 
                                    target="_blank" 
                                    rel="noreferrer" 
                                    style={styles.link}
                                >
                                    Developer Portal
                                </a>
                            </div>
                        </div>
                    </div>

                    {/* Feature Entitlements Card */}
                    <div style={styles.card}>
                        <h2 style={styles.cardTitle}>Active Entitlements</h2>
                        <p style={styles.cardDescription}>
                            List of software features enabled under your current billing package tier.
                        </p>

                        <div style={styles.featureList}>
                            <div style={styles.featureItem}>
                                <div style={styles.featureLeft}>
                                    <span style={styles.featureIcon}>📋</span>
                                    <div>
                                        <div style={styles.featureName}>Attendance Tracking</div>
                                        <div style={styles.featureDesc}>Log employee check-in times and run reports.</div>
                                    </div>
                                </div>
                                <span style={{
                                    ...styles.badge,
                                    backgroundColor: capabilities.attendance ? 'rgba(46, 204, 113, 0.15)' : 'rgba(231, 76, 60, 0.15)',
                                    color: capabilities.attendance ? '#2ecc71' : '#e74c3c'
                                }}>
                                    {capabilities.attendance ? 'Enabled' : 'Locked'}
                                </span>
                            </div>

                            <div style={styles.featureItem}>
                                <div style={styles.featureLeft}>
                                    <span style={styles.featureIcon}>🔍</span>
                                    <div>
                                        <div style={styles.featureName}>Smart Search</div>
                                        <div style={styles.featureDesc}>Search employees by VLM-processed descriptions.</div>
                                    </div>
                                </div>
                                <span style={{
                                    ...styles.badge,
                                    backgroundColor: capabilities.search ? 'rgba(46, 204, 113, 0.15)' : 'rgba(231, 76, 60, 0.15)',
                                    color: capabilities.search ? '#2ecc71' : '#e74c3c'
                                }}>
                                    {capabilities.search ? 'Enabled' : 'Locked'}
                                </span>
                            </div>

                            <div style={styles.featureItem}>
                                <div style={styles.featureLeft}>
                                    <span style={styles.featureIcon}>🤖</span>
                                    <div>
                                        <div style={styles.featureName}>VLM Summarization</div>
                                        <div style={styles.featureDesc}>Summarize insights and anomalies utilizing AI.</div>
                                    </div>
                                </div>
                                <span style={{
                                    ...styles.badge,
                                    backgroundColor: capabilities.summarization ? 'rgba(46, 204, 113, 0.15)' : 'rgba(231, 76, 60, 0.15)',
                                    color: capabilities.summarization ? '#2ecc71' : '#e74c3c'
                                }}>
                                    {capabilities.summarization ? 'Enabled' : 'Locked'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
};

const styles = {
    container: {
        padding: '24px',
        color: '#1e293b',
        fontFamily: "'Inter', sans-serif",
    },
    grid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
        gap: '24px',
        marginTop: '16px',
    },
    card: {
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: '16px',
        padding: '32px',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03)',
    },
    cardTitle: {
        fontSize: '20px',
        fontWeight: '600',
        margin: '0 0 8px 0',
        color: '#0f172a',
    },
    cardDescription: {
        fontSize: '13px',
        color: '#64748b',
        lineHeight: '1.5',
        margin: '0 0 24px 0',
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
    },
    label: {
        fontSize: '12px',
        fontWeight: '600',
        color: '#475569',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
    },
    input: {
        background: '#f8fafc',
        border: '1px solid #cbd5e1',
        borderRadius: '8px',
        padding: '12px 16px',
        color: '#0f172a',
        fontSize: '14px',
        fontFamily: 'monospace',
        outline: 'none',
    },
    button: {
        background: '#386E9D',
        color: '#ffffff',
        border: 'none',
        borderRadius: '8px',
        padding: '12px',
        fontSize: '14px',
        fontWeight: '600',
        cursor: 'pointer',
        transition: 'background-color 0.2s',
    },
    successAlert: {
        backgroundColor: 'rgba(46, 204, 113, 0.15)',
        border: '1px solid rgba(46, 204, 113, 0.3)',
        borderRadius: '8px',
        color: '#27ae60',
        padding: '12px',
        fontSize: '13px',
        marginTop: '16px',
        textAlign: 'center',
    },
    statusBox: {
        borderTop: '1px solid #e2e8f0',
        marginTop: '24px',
        paddingTop: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
    },
    statusRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '13px',
    },
    statusLabel: {
        color: '#64748b',
    },
    statusValue: {
        fontWeight: '600',
    },
    link: {
        color: '#386E9D',
        textDecoration: 'none',
        fontWeight: '500',
    },
    featureList: {
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
    },
    featureItem: {
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        padding: '16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
    featureLeft: {
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
    },
    featureIcon: {
        fontSize: '24px',
    },
    featureName: {
        fontSize: '14px',
        fontWeight: '600',
        color: '#0f172a',
        marginBottom: '2px',
    },
    featureDesc: {
        fontSize: '12px',
        color: '#64748b',
    },
    badge: {
        fontSize: '11px',
        fontWeight: '600',
        padding: '4px 10px',
        borderRadius: '6px',
        textTransform: 'uppercase',
    }
};

export default Settings;
