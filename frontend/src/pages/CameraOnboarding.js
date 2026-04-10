import React, { useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { cameraAPI } from '../api/camera';
import './CameraOnboarding.css';

const CameraOnboarding = () => {
    const [camera, setCamera] = useState({
        room: '',
        building: '',
        mac_address: '',
        username: '',
        password: ''
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitStatus, setSubmitStatus] = useState(null); // 'success', 'error', or null
    const [errorMessage, setErrorMessage] = useState('');

    const handleChange = (field, value) => {
        setCamera({ ...camera, [field]: value });
    };

    const handleSubmit = async () => {
        setSubmitStatus(null);
        setErrorMessage('');

        if (!camera.room || !camera.building || !camera.mac_address || !camera.username || !camera.password) {
            setSubmitStatus('error');
            setErrorMessage('All fields are required.');
            return;
        }

        setIsSubmitting(true);

        try {
            const formData = new FormData();
            formData.append('room', camera.room);
            formData.append('building', camera.building);
            formData.append('mac_address', camera.mac_address);
            formData.append('username', camera.username);
            formData.append('password', camera.password);

            await cameraAPI.createCamera(formData);
            
            setSubmitStatus('success');
            setCamera({ room: '', building: '', mac_address: '', username: '', password: '' }); // Reset form
            setTimeout(() => setSubmitStatus(null), 3000);
        } catch (error) {
            console.error("Submission error:", error);
            setSubmitStatus('error');
            const msg = error.response?.data?.detail || error.message || 'Failed to onboard camera.';
            setErrorMessage(msg);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <DashboardLayout title="Camera Onboarding">
            <div className="onboarding-container">
                <div className="onboarding-header">
                    <h2>Onboard Camera</h2>
                    <p>Enter the credentials and location details for the new network camera.</p>
                </div>

                {submitStatus === 'success' && (
                    <div className="status-message success">
                        Camera successfully onboarded!
                    </div>
                )}
                {submitStatus === 'error' && errorMessage && (
                    <div className="status-message error">
                        {errorMessage}
                    </div>
                )}

                <div className="camera-onboarding-card">
                    <div className="details-form">
                        <div className="form-group">
                            <label>Room</label>
                            <input
                                type="text"
                                value={camera.room}
                                onChange={(e) => handleChange('room', e.target.value)}
                                placeholder="e.g. Conference Room A"
                            />
                        </div>
                        <div className="form-group">
                            <label>Building</label>
                            <input
                                type="text"
                                value={camera.building}
                                onChange={(e) => handleChange('building', e.target.value)}
                                placeholder="e.g. Building 1"
                            />
                        </div>
                        <div className="form-group">
                            <label>MAC Address</label>
                            <input
                                type="text"
                                value={camera.mac_address}
                                onChange={(e) => handleChange('mac_address', e.target.value)}
                                placeholder="e.g. 00:1A:2B:3C:4D:5E"
                            />
                        </div>
                        <div className="form-group">
                            <label>Username</label>
                            <input
                                type="text"
                                value={camera.username}
                                onChange={(e) => handleChange('username', e.target.value)}
                                placeholder="Camera Admin Username"
                            />
                        </div>
                        <div className="form-group">
                            <label>Password</label>
                            <input
                                type="password"
                                value={camera.password}
                                onChange={(e) => handleChange('password', e.target.value)}
                                placeholder="Camera Admin Password"
                            />
                        </div>
                    </div>
                    <div className="onboarding-actions">
                        <button
                            className="btn-submit"
                            onClick={handleSubmit}
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Onboarding...' : 'Onboard Camera'}
                        </button>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default CameraOnboarding;
