import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const LoginModal = ({ isOpen, onClose, onSwitchToRegister }) => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const navigate = useNavigate();

    if (!isOpen) return null;

    const isValid = email.trim() !== '' && password.trim() !== '';

    const handleSubmit = (e) => {
        e.preventDefault();
        if (isValid) {
            // Mock login handling
            if (email === 'superadmin@superadmin.com') {
                navigate('/dashboard/all-employees');
            } else {
                navigate('/dashboard/video-feed');
            }
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button className="modal-close" onClick={onClose}>×</button>
                <h2 className="modal-title">Log in</h2>

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
                        disabled={!isValid}
                    >
                        Login
                    </button>
                </form>

                <button className="modal-btn-google">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg" alt="G" style={{ width: '20px' }} />
                    Continue with Google
                </button>

                <div className="modal-footer">
                    New To Eagle Eye? <span className="modal-link" onClick={onSwitchToRegister}>Create account</span>
                </div>
            </div>
        </div>
    );
};

export default LoginModal;
