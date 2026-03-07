import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const RegisterModal = ({ isOpen, onClose, onSwitchToLogin }) => {
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const navigate = useNavigate();

    if (!isOpen) return null;

    const isValid = fullName.trim() !== '' && email.trim() !== '' && password.trim() !== '';

    const handleSubmit = (e) => {
        e.preventDefault();
        if (isValid) {
            // Mock register handling
            navigate('/dashboard/video-feed');
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button className="modal-close" onClick={onClose}>×</button>
                <h2 className="modal-title">Sign up</h2>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <input
                            type="text"
                            placeholder="Full Name"
                            className="form-input"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                        />
                    </div>
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

                    <div className="terms-checkbox">
                        <input type="checkbox" id="terms" />
                        <label htmlFor="terms">
                            I agree to Eagle Eye's <a href="#terms" className="terms-link">Terms of Service</a>, <a href="#privacy" className="terms-link">Privacy Policy</a> and <a href="#content" className="terms-link">Content Policies</a>
                        </label>
                    </div>

                    <button
                        className={`modal-btn-primary ${isValid ? 'active' : ''}`}
                        disabled={!isValid}
                    >
                        Create Account
                    </button>
                </form>

                <div className="modal-divider">or</div>

                <button className="modal-btn-google">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg" alt="G" style={{ width: '20px' }} />
                    Continue with Google
                </button>

                <div className="modal-footer">
                    Already have an account? <span className="modal-link" onClick={onSwitchToLogin}>Log in</span>
                </div>
            </div>
        </div>
    );
};

export default RegisterModal;
