// src/pages/Team.js
import React, { useState } from 'react';
import './Team.css';
import LoginModal from '../components/modals/LoginModal';
import Footer from '../components/Footer';
function Team() {
  const [activeModal, setActiveModal] = useState(null);
  const openLogin = () => setActiveModal('login');
  const closeModal = () => setActiveModal(null);

  const teamMembers = [
    {
      name: 'Abd Elrahman',
      id: '202201023',
      role: 'Software Engineer',
      description: 'Backend & Frontend Development',
      icon: '👨‍💻'
    },
    {
      name: 'Bosy Ayman',
      id: '202202076',
      role: 'CV & Video Analytics',
      description: 'Computer Vision & AI',
      icon: '👩‍💻'
    },
    {
      name: 'Shahd Hossam',
      id: '202100936',
      role: 'Software Engineer',
      description: 'Backend & Frontend Development',
      icon: '👩‍💻'
    },
    {
      name: 'Habiba Mohamed',
      id: '202201684',
      role: 'CV & Video Analytics',
      description: 'Computer Vision & AI',
      icon: '👩‍💻'
    }
  ];

  return (
    <div className="team-page">
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

      {/* Hero – white background, dark text */}
      <section className="team-hero">
        <div className="container">
          <h1>Our Team</h1>
          <p>Passionate innovators behind Rawi Vision</p>
        </div>
      </section>

      {/* Team Members Grid */}
      <section className="team-section">
        <div className="container">
          <div className="team-grid">
            {teamMembers.map((member, index) => (
              <div className="team-card" key={index}>
                <div className="team-avatar">{member.icon}</div>
                <h3>{member.name}</h3>
                <p className="team-id">{member.id}</p>
                <p className="team-role">{member.role}</p>
                <p className="team-desc">{member.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Supervisor Section */}
      <section className="supervisor-section">
        <div className="container">
          <div className="supervisor-card">
            <div className="supervisor-icon">👩‍🏫</div>
            <h3>Supervised by</h3>
            <p className="supervisor-name">Dr. Doaa Shawky</p>
            <p className="supervisor-title">Project Supervisor</p>
          </div>
        </div>
      </section>
      <Footer/>

      <LoginModal isOpen={activeModal === 'login'} onClose={closeModal} />
    </div>
  );
}

export default Team;