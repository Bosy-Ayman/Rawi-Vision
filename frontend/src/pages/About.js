import React, { useState } from 'react';
import './About.css';
import LoginModal from '../components/modals/LoginModal';
import Footer from '../components/Footer';  

function About() {
  const [activeModal, setActiveModal] = useState(null);

  const openLogin = () => setActiveModal('login');
  const closeModal = () => setActiveModal(null);

  return (
    <div className="about-page">
      {/* Header */}
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

      {/* Hero – flush with header */}
      <section className="about-hero">
        <div className="container">
          <h1>About Rawi Vision</h1>
          <p>Real-time Video Analysis Platform powered by AI</p>
        </div>
      </section>

      {/* Who We Are */}
      <section className="about-section">
        <div className="container">
          <div className="content-card">
            <h2>Who We Are</h2>
            <p>
              Rawi Vision is a comprehensive Real-time Video Analysis Platform designed to automate 
              the extraction of meaningful insights from surveillance feeds. By integrating Face Recognition, 
              Smart Search, Video Summarization, and Anomaly Detection, we enhance situational awareness 
              and security for businesses.
            </p>
          </div>
        </div>
      </section>

      {/* Mission & Vision */}
      <section className="about-section">
        <div className="container">
          <div className="mission-vision">
            <div className="card">
              <div className="card-icon">🎯</div>
              <h3>Our Mission</h3>
              <p>To provide intelligent, reliable surveillance solutions that enhance security and operational efficiency through AI.</p>
            </div>
            <div className="card">
              <div className="card-icon">👁️</div>
              <h3>Our Vision</h3>
              <p>To become the global leader in AI-powered surveillance technology, creating safer environments worldwide.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Project Overview */}
      <section className="about-section">
        <div className="container">
          <div className="content-card">
            <h2>Project Overview</h2>
            <p>
              <strong>Graduation Project</strong> supervised by <strong>Dr. Doaa Shawky</strong><br />
              Built with FastAPI, React, PostgreSQL (pgvector), YOLOv8, and modern AI pipelines.
            </p>
          </div>
        </div>
      </section>

      <Footer />

      <LoginModal isOpen={activeModal === 'login'} onClose={closeModal} />
    </div>
  );
}

export default About;