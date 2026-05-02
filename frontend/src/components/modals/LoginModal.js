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

    const handleGoogleSuccess = async (credentialResponse) => {
        setIsLoading(true);
        setErrorMsg('');
        try {
            // Send the Google ID token to our backend
            const response = await authAPI.loginWithGoogle(credentialResponse.credential);

            // Save the JWT we get back
            localStorage.setItem('access_token', response.access_token);
            localStorage.setItem('user_role', response.role);
            localStorage.setItem('full_name', response.full_name);

            onClose();

            // Route based on role
            if (response.role === 'HR') {
                navigate('/dashboard/employee-onboarding');
            } else if (response.role === 'Manager') {
                navigate('/dashboard/video-feed');
            } else {
                navigate('/dashboard/video-feed'); // fallback
            }
        } catch (err) {
            setErrorMsg(err.detail || 'Login failed. You may not be registered in the system.');
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) return null;

    const isValid = email.trim() !== '' && password.trim() !== '';

    const handleSubmit = (e) => {
        e.preventDefault();
        if (isValid) {
            // Placeholder for manual email/password login
            if (email === 'superadmin@superadmin.com') {
                navigate('/admin/system-users');
            } else if (email === 'hr@hr.com') {
                navigate('/dashboard/employee-onboarding');
            } else {
                navigate('/dashboard/video-feed');
            }
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button className="modal-close" onClick={onClose} disabled={isLoading}>×</button>
                <h2 className="modal-title">Log in</h2>

                {errorMsg && <div className="sum-alert sum-alert--error" style={{ marginBottom: '15px', color: 'red', fontSize: '14px', textAlign: 'center' }}>{errorMsg}</div>}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <input
                            type="email"
                            placeholder="Email"
                            className="form-input"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>
                    <div className="form-group">
                        <input
                            type="password"
                            placeholder="Password"
                            className="form-input"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                        />
                    </div>

                    <button
                        className={`modal-btn-primary ${isValid ? 'active' : ''}`}
                        disabled={!isValid || isLoading}
                    >
                        {isLoading ? 'Processing...' : 'Login'}
                    </button>
                </form>

                <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', height: '40px' }}>
                    <GoogleLogin
                        onSuccess={handleGoogleSuccess}
                        onError={() => setErrorMsg('Google Login Failed')}
                        theme="filled_blue"
                        shape="rectangular"
                        text="continue_with"
                        width="300"
                    />
                </div>
            </div>
        </div>
    );
};

export default LoginModal;
