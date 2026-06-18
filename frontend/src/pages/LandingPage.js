import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import '../App.css';
import LoginModal from '../components/modals/LoginModal';
import Footer from '../components/Footer';  
function LandingPage() {
    const [activeModal, setActiveModal] = useState(null); // 'login' or null

    const openLogin = () => setActiveModal('login');
    const closeModal = () => setActiveModal(null);

    const features = [
        {
            id: 1,
            icon: '👤',
            iconPlaceholder: 'attendance_icon.svg',
            title: 'Automated smart attendance',
            description: 'Employees can punch in and punch out without the need for any physical contact. Our system is integrated with any organization\'s database.'
        },
        {
            id: 2,
            icon: '📋',
            iconPlaceholder: 'summarization-icon.svg',
            title: 'Intelligent Video Summarization',
            description: 'Analyze lengthy surveillance videos and receive brief, relevant summaries, saving time and enhancing the review process.'
        },
        {
            id: 3,
            icon: '⚠️',
            iconPlaceholder: 'anomaly-icon.svg',
            title: 'Real-Time Anomaly Detection',
            description: 'Send real-time anomaly detection alerts to users via email to mitigate risks and keep them take timely action safety as a top priority.'
        },
        {
            id: 4,
            icon: '🔍',
            iconPlaceholder: 'search-icon.svg',
            title: 'Semantic Video Search',
            description: 'Find exactly what you are looking for. Search through hours of footage using natural language (e.g., "Show me who entered the server room at night yesterday").'
        },
        {
            id: 5,
            icon: '📊',
            iconPlaceholder: 'insights-icon.svg',
            title: 'Employee Performance Insights',
            description: 'Track employee attendance trends, identify top performers, and identify attendance and productivity patterns.'
        }
    ];

    return (
        <div className="landing-page">
            {/* ==================== HEADER ==================== */}
            <header className="header">
                <div className="header-container">
                    <div className="logo">
                        <img src="/assets/images/logo.svg" alt="Rawi Vision Logo" />
                    </div>

                    <nav className="nav-buttons">
                        <button className="btn-login" onClick={openLogin}>Log In</button>
                    </nav>
                </div>
            </header>

            {/* ==================== HERO SECTION ==================== */}
            <section className="hero">
                <div className="hero-container">
                    <div className="hero-content">
                        <div className="hero-box">
                            <h1 className="hero-title">
                                <span className="main-text">A Complete solution</span>
                                <span className="for-text">for all your</span>
                                <span className="highlight-text">Surveillance</span>
                                <span className="needs-text">needs</span>
                            </h1>
                        </div>
                    </div>

                    <div className="hero-image">
                        <img src="/assets/images/camera.png" alt="Security Camera" className="camera-img" />
                    </div>
                </div>

                <div className="divider">
                    <div className="divider-camera">📹</div>
                </div>
            </section>

            {/* ==================== FEATURES SECTION ==================== */}
            <section className="features">
                <div className="features-container">
                    <div className="features-header">
                        <h2 className="features-tagline">
                            <span className="brand-name">RAWI VISION</span>{' '}
                            <span className="tagline-text">SMARTER VISION BETTER MANAGEMENT.</span>
                        </h2>
                    </div>

                    <div className="features-grid">
                        {features.map((feature) => (
                            <div key={feature.id} className="feature-card">
                                <div className="feature-icon">
                                    <img src={`/assets/icons/${feature.iconPlaceholder}`} alt={feature.title} />
                                </div>
                                <h3 className="feature-title">{feature.title}</h3>
                                <p className="feature-description">{feature.description}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ==================== FOOTER ==================== */}
            <Footer/>

            {/* ==================== MODALS ==================== */}
            <LoginModal
                isOpen={activeModal === 'login'}
                onClose={closeModal}
            />
        </div>
    );
}

export default LandingPage;
