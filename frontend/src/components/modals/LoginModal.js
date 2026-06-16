import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { authAPI } from '../../api/auth';

const LoginModal = ({ isOpen, onClose }) => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [errorMsg, setErrorMsg] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    if (!isOpen) return null;

    const isValid = email.trim() !== '' && password.trim() !== '';

    const handleNavigation = (role) => {
        if (role === 'HR') {
            navigate('/dashboard/employee-onboarding');
        } else if (role === 'Manager') {
            navigate('/dashboard/video-feed');
        } else {
            navigate('/dashboard/video-feed');
        }
    };

    const handleGoogleSuccess = async (credentialResponse) => {
        setIsLoading(true);
        setErrorMsg('');
        try {
            const response = await authAPI.loginWithGoogle(
                credentialResponse.credential
            );
            localStorage.setItem('access_token', response.access_token);
            localStorage.setItem('user_role', response.role);
            localStorage.setItem('full_name', response.full_name);
            if (response.profile_image_url) {
                localStorage.setItem('user_avatar', response.profile_image_url);
            }
            onClose();
            handleNavigation(response.role);
        } catch (err) {
            setErrorMsg(
                err?.detail || 'Login failed. User not registered.'
            );
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        setErrorMsg('');
        if (!isValid) return;

        // Fake/manual login (replace later with API)
        if (email === 'superadmin@superadmin.com') {
            navigate('/admin/system-users');
        } else if (email === 'hr@hr.com') {
            navigate('/dashboard/employee-onboarding');
        } else {
            navigate('/dashboard/video-feed');
        }
        onClose();
    };

    // Updated Inline Styles - Larger Modal
    const styles = {
        overlay: {
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
        },
        content: {
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25)',
            width: '100%',
            maxWidth: '550px',           // Increased width
            padding: '80px 46px',        // More padding
            position: 'relative',
            animation: 'modalPop 0.3s ease',
        },
        closeBtn: {
            position: 'absolute',
            top: '20px',
            right: '24px',
            fontSize: '32px',
            fontWeight: '300',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#666',
            lineHeight: 1,
            padding: '4px 10px',
        },
        title: {
            margin: '0 0 32px 0',
            textAlign: 'center',
            fontSize: '32px',            // Larger title
            fontWeight: 700,
            color: '#1f2937',
        },
        error: {
            padding: '14px 18px',
            backgroundColor: '#fee2e2',
            color: '#dc2626',
            borderRadius: '8px',
            marginBottom: '24px',
            fontSize: '15px',
        },
        formGroup: {
            marginBottom: '22px',
        },
        input: {
            width: '100%',
            padding: '16px 18px',
            border: '1px solid #d1d5db',
            borderRadius: '10px',
            fontSize: '16px',
            transition: 'all 0.2s',
            outline: 'none',
        },
        button: {
            width: '100%',
            padding: '16px',
            fontSize: '17px',
            fontWeight: 600,
            border: 'none',
            borderRadius: '10px',
            cursor: 'pointer',
            transition: 'all 0.2s',
            marginBottom: '24px',
        },
        buttonActive: {
            backgroundColor: '#3b82f6',
            color: 'white',
        },
        buttonDisabled: {
            backgroundColor: '#9ca3af',
            color: 'white',
            cursor: 'not-allowed',
        },
        googleWrapper: {
            display: 'flex',
            justifyContent: 'center',
            marginTop: '8px',
        },
    };

    return (
        <div style={styles.overlay} onClick={onClose}>
            <div
                style={styles.content}
                onClick={(e) => e.stopPropagation()}
            >
                <button
                    style={styles.closeBtn}
                    onClick={onClose}
                    disabled={isLoading}
                >
                    ×
                </button>

                <h2 style={styles.title}>Log in</h2>

                {errorMsg && (
                    <div style={styles.error}>
                        {errorMsg}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div style={styles.formGroup}>
                        <input
                            type="email"
                            placeholder="Email"
                            style={styles.input}
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            disabled={isLoading}
                        />
                    </div>
                    <div style={styles.formGroup}>
                        <input
                            type="password"
                            placeholder="Password"
                            style={styles.input}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            disabled={isLoading}
                        />
                    </div>

                    <button
                        type="submit"
                        style={{
                            ...styles.button,
                            ...(isValid && !isLoading ? styles.buttonActive : styles.buttonDisabled),
                        }}
                        disabled={!isValid || isLoading}
                    >
                        {isLoading ? 'Processing...' : 'Login'}
                    </button>
                </form>

                <div style={styles.googleWrapper}>
                    <GoogleLogin
                        onSuccess={handleGoogleSuccess}
                        onError={() => setErrorMsg('Google Login Failed')}
                        theme="filled_blue"
                        shape="rectangular"
                        text="continue_with"
                        width="860"   // Wider Google button
                    />
                </div>
            </div>
        </div>
    );
};

export default LoginModal;