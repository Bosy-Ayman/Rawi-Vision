import React from 'react';
import './About.css'; // or keep styles in App.css

function About() {
  return (
    <div className="about-page">
      {/* Hero */}
      <section className="about-hero">
        <div className="container">
          <h1>About Rawi Vision</h1>
          <p>Real-time Video Analysis Platform powered by AI</p>
        </div>
      </section>

      {/* Company Overview */}
      <section className="about-section">
        <div className="container">
          <h2>Who We Are</h2>
          <p>
            Rawi Vision is a comprehensive Real-time Video Analysis Platform designed to automate 
            the extraction of meaningful insights from surveillance feeds. By integrating Face Recognition, 
            Smart Search, Video Summarization, and Anomaly Detection, we enhance situational awareness 
            and security for businesses.
          </p>
        </div>
      </section>

      {/* Mission & Vision */}
      <section className="about-section bg-light">
        <div className="container">
          <div className="mission-vision">
            <div className="card">
              <h3>🎯 Our Mission</h3>
              <p>To provide intelligent, reliable surveillance solutions that enhance security and operational efficiency through AI.</p>
            </div>
            <div className="card">
              <h3>👁️ Our Vision</h3>
              <p>To become the global leader in AI-powered surveillance technology, creating safer environments worldwide.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Supervisor & Team Context */}
      <section className="about-section">
        <div className="container">
          <h2>Project Overview</h2>
          <p>
            <strong>Graduation Project</strong> supervised by <strong>Dr. Doaa Shawky</strong><br />
            Built with FastAPI, React, PostgreSQL (pgvector), YOLOv8, and modern AI pipelines.
          </p>
        </div>
      </section>
    </div>
  );
}

export default About;