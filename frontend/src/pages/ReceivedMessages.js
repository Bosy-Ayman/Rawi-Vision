import React, { useState, useEffect } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import './ReceivedMessages.css';

const ReceivedMessages = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchMessages();
  }, []);

  const fetchMessages = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8002/api/contact/messages', {
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Unauthorized. Please ensure you are logged in as an HR/Admin user.');
        }
        throw new Error(`Failed to fetch messages: ${response.status}`);
      }

      const data = await response.json();
      setMessages(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching messages:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (loading) {
    return <DashboardLayout title="Received Messages"><div className="loading">Loading messages...</div></DashboardLayout>;
  }

  return (
    <DashboardLayout title="Received Messages">
      <div className="received-messages-container">
        <div className="header-section">
          <h1>Received Messages</h1>
          <p>All contact form submissions</p>
          <button className="refresh-btn" onClick={fetchMessages}>
            Refresh
          </button>
        </div>

      {error && (
        <div className="error-message">
          <span>⚠️ {error}</span>
        </div>
      )}

      {messages.length === 0 ? (
        <div className="no-messages">
          <p>No messages received yet</p>
        </div>
      ) : (
        <div className="messages-table-wrapper">
          <table className="messages-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Email</th>
                <th>Subject</th>
                <th>Date</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {messages.map((msg, index) => (
                <React.Fragment key={msg.id}>
                  <tr className={expandedId === msg.id ? 'expanded' : ''}>
                    <td className="id-col">{index + 1}</td>
                    <td className="name-col">{msg.name}</td>
                    <td className="email-col">
                      <a href={`mailto:${msg.email}`}>{msg.email}</a>
                    </td>
                    <td className="subject-col">{msg.subject || '(no subject)'}</td>
                    <td className="date-col">{formatDate(msg.created_at)}</td>
                    <td className="action-col">
                      <button
                        className="expand-btn"
                        onClick={() => toggleExpand(msg.id)}
                      >
                        {expandedId === msg.id ? '⬆ Hide' : '⬇ View'}
                      </button>
                    </td>
                  </tr>
                  {expandedId === msg.id && (
                    <tr className="expanded-row">
                      <td colSpan="6">
                        <div className="message-details">
                          <div className="detail-item">
                            <strong>From:</strong> {msg.name} ({msg.email})
                          </div>
                          <div className="detail-item">
                            <strong>Subject:</strong> {msg.subject || '(no subject)'}
                          </div>
                          <div className="detail-item">
                            <strong>Date:</strong> {formatDate(msg.created_at)}
                          </div>
                          <div className="detail-item message-content">
                            <strong>Message:</strong>
                            <p>{msg.message}</p>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </div>
    </DashboardLayout>
  );
};

export default ReceivedMessages;
