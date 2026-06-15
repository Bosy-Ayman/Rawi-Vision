// src/pages/Contact.js
import React, { useState } from 'react';
import './Contact.css';
import LoginModal from '../components/modals/LoginModal';

function Contact() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    message: ''
  });
  const [status, setStatus] = useState(null);
  const [activeModal, setActiveModal] = useState(null);

  const openLogin = () => setActiveModal('login');
  const closeModal = () => setActiveModal(null);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus('sending');
    setTimeout(() => {
      setStatus('sent');
      setFormData({ name: '', email: '', subject: '', message: '' });
      setTimeout(() => setStatus(null), 3000);
    }, 1000);
  };

  return (
    <div className="contact-page">
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

      <section className="contact-hero">
        <div className="container">
          <h1>Let's Talk</h1>
          <p>Have a project in mind or need support? We're here to help.</p>
        </div>
      </section>

      <section className="contact-main">
        <div className="container">
          <div className="contact-grid">
            {/* LEFT: Contact info with cards */}
            <div className="contact-info-card">
              <h2>Get in touch</h2>
              <div className="info-list">
                <div className="info-row">
                  <div className="info-icon">📍</div>
                  <div><strong>Visit us</strong><br />Cairo, Egypt – Smart Village, Building B2</div>
                </div>
                <div className="info-row">
                  <div className="info-icon">📧</div>
                  <div><strong>Email</strong><br />hello@rawivision.com<br />support@rawivision.com</div>
                </div>
                <div className="info-row">
                  <div className="info-icon">📞</div>
                  <div><strong>Phone</strong><br />+20 123 456 7890<br />+20 114 567 8901</div>
                </div>
                <div className="info-row">
                  <div className="info-icon">🕒</div>
                  <div><strong>Business hours</strong><br />Sun – Thu: 9:00 AM – 6:00 PM<br />Fri – Sat: closed</div>
                </div>
              </div>
              <div className="quick-contact-cards">
                <div className="quick-card">💬 Sales<br /><span>sales@rawivision.com</span></div>
                <div className="quick-card">🛠️ Tech<br /><span>tech@rawivision.com</span></div>
                <div className="quick-card">🤝 Partner<br /><span>partner@rawivision.com</span></div>
              </div>
            </div>

            {/* RIGHT: Contact form */}
            <form className="contact-form-card" onSubmit={handleSubmit}>
              <h2>Send us a message</h2>
              <div className="form-group">
                <input type="text" name="name" placeholder="Full name *" value={formData.name} onChange={handleChange} required />
              </div>
              <div className="form-group">
                <input type="email" name="email" placeholder="Email address *" value={formData.email} onChange={handleChange} required />
              </div>
              <div className="form-group">
                <input type="text" name="subject" placeholder="Subject" value={formData.subject} onChange={handleChange} />
              </div>
              <div className="form-group">
                <textarea name="message" placeholder="How can we help you? *" rows="5" value={formData.message} onChange={handleChange} required></textarea>
              </div>
              <button type="submit" className="btn-submit" disabled={status === 'sending'}>
                {status === 'sending' ? 'Sending...' : 'Send Message'}
              </button>
              {status === 'sent' && <p className="success-msg">✓ Message sent! We'll reply soon.</p>}
            </form>
          </div>
        </div>
      </section>

      {/* Map section for contrast */}
      <section className="contact-map">
        <div className="container">
          <h3>Find us</h3>
          <div className="map-wrapper">
            <iframe
              title="Rawi Vision Location"
              src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3455.123456789012!2d31.200000!3d30.000000!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMzDCsDAwJzAwLjAiTiAzMcKwMTInMDAuMCJF!5e0!3m2!1sen!2seg!4v1234567890"
              width="100%"
              height="280"
              style={{ border: 0 }}
              allowFullScreen=""
              loading="lazy"
            ></iframe>
          </div>
        </div>
      </section>

      <LoginModal isOpen={activeModal === 'login'} onClose={closeModal} />
    </div>
  );
}

export default Contact;