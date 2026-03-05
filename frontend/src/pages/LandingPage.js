import React, { useState } from 'react';
import '../App.css';
import LoginModal from '../components/modals/LoginModal';

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
            <footer className="footer">
                <div className="footer-container">
                    <div className="footer-content">
                        {/* Logo Section */}
                        <div className="footer-section footer-logo-section">
                            <div className="footer-logo">
                                <img src="/assets/images/logo.svg" alt="Rawi Vision Logo" style={{ height: '40px' }} />
                            </div>
                        </div>

                        {/* Company Links */}
                        <div className="footer-section">
                            <h4 className="footer-heading">COMPANY</h4>
                            <ul className="footer-links">
                                <li><a href="#about">About</a></li>
                                <li><a href="#services">Services</a></li>
                                <li><a href="#products">Products</a></li>
                                <li><a href="#gallery">Gallery</a></li>
                                <li><a href="#team">Our Team</a></li>
                                <li><a href="#contact">Contact Us</a></li>
                            </ul>
                        </div>
                    </div>

                    {/* Social Media & Copyright */}
                    <div className="footer-bottom">
                        <div className="social-links">
                            <a href="#instagram" className="social-icon" aria-label="Instagram">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
                                </svg>
                            </a>
                            <a href="#facebook" className="social-icon" aria-label="Facebook">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                                </svg>
                            </a>
                            <a href="#youtube" className="social-icon" aria-label="YouTube">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                                </svg>
                            </a>
                            <a href="#twitter" className="social-icon" aria-label="Twitter">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                                </svg>
                            </a>
                            <a href="#linkedin" className="social-icon" aria-label="LinkedIn">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h5v-8.306c0-4.613 5.48-4.515 5.48 0v8.306h5v-10.515c0-8.59-10.33-7.461-10.512-3.626v-1.865z" />
                                </svg>
                            </a>
                        </div>

                        <div className="footer-legal">
                            <p className="copyright">
                                By continuing past this page, you agree to our Terms of Service, Cookie Policy, Privacy Policy and Content Policies. All trademarks are properties of their respective owners. <br />
                                2025-2026 © Rawi Vision™ Ltd. All rights reserved.
                            </p>
                        </div>
                    </div>
                </div>
            </footer>

            {/* ==================== MODALS ==================== */}
            <LoginModal
                isOpen={activeModal === 'login'}
                onClose={closeModal}
            />
        </div>
    );
}

export default LandingPage;
