import React, { useState, useEffect } from 'react';
import { summarizationApi } from '../api/summarization';
import { searchAPI } from '../api/search';
import ToastNotification from '../components/modals/ToastNotification';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import './Summarization.css';

const Summarization = () => {
  const [videos, setVideos] = useState([]);
  const [summaries, setSummaries] = useState({});
  const [autoSummarize, setAutoSummarize] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeVideoUrl, setActiveVideoUrl] = useState(null);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const showToast = (type, title, message) => {
    setNotification({ type, title, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch auto settings
      const settings = await summarizationApi.getAutoSettings();
      setAutoSummarize(settings.auto_summarize);

      // Fetch all recorded videos from search API
      const vids = await searchAPI.listVideos();
      setVideos(vids || []);

      // Fetch all summaries
      const sumsList = await summarizationApi.listSummaries();
      const sumsMap = {};
      (sumsList || []).forEach(s => {
        sumsMap[s.video_id] = s;
      });
      setSummaries(sumsMap);
    } catch (error) {
      showToast('error', 'Error', 'Failed to load summarization data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAuto = async () => {
    const newValue = !autoSummarize;
    setAutoSummarize(newValue);
    try {
      await summarizationApi.updateAutoSettings(newValue);
      showToast('success', 'Settings Updated', `Auto-Summarize turned ${newValue ? 'ON' : 'OFF'}`);
    } catch (error) {
      setAutoSummarize(!newValue); // revert
      showToast('error', 'Error', 'Failed to update setting');
    }
  };

  const handleGenerate = async (video) => {
    try {
      showToast('info', 'Generating', 'Triggering summarization...');
      const newSummary = await summarizationApi.generateSummary(video.id, video.camera_id, video.storage_path);
      setSummaries(prev => ({
        ...prev,
        [video.id]: newSummary
      }));
      showToast('success', 'Started', 'Summarization task started!');
      
    } catch (error) {
      showToast('error', 'Error', error.detail || 'Failed to trigger summarization');
    }
  };

  const getStatusClass = (status) => {
    switch (status) {
      case 'completed': return 'status-completed';
      case 'failed': return 'status-failed';
      case 'processing': return 'status-processing';
      default: return 'status-pending';
    }
  };

  return (
    <DashboardLayout title="Video Summarization">
      <div className="summarization-container">
        {notification && (
        <ToastNotification
          type={notification.type}
          title={notification.title}
          message={notification.message}
          onClose={() => setNotification(null)}
        />
      )}
      
      <div className="summarization-header">
        <p style={{ margin: 0, color: '#aaa', fontSize: '1.1rem' }}>Condense hours of footage into minutes using AI</p>
        <div className="auto-toggle">
          <span>Auto-Summarize New Videos</span>
          <label className="switch">
            <input 
              type="checkbox" 
              checked={autoSummarize} 
              onChange={handleToggleAuto} 
              disabled={loading}
            />
            <span className="slider round"></span>
          </label>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px' }}>Loading...</div>
      ) : (
        <div className="video-grid">
          {videos.map(video => {
            const summary = summaries[video.id];
            
            return (
              <div key={video.id} className="video-card">
                <h3>{video.filename}</h3>
                <p>Camera: {video.camera_id}</p>
                
                {summary && (
                  <div className={`status-badge ${getStatusClass(summary.status)}`}>
                    Summary: {summary.status.toUpperCase()}
                  </div>
                )}
                
                <div className="card-actions">
                  {!summary || summary.status === 'failed' ? (
                    <button 
                      className="btn-generate"
                      onClick={() => handleGenerate(video)}
                    >
                      ⚙️ On Demand Generate
                    </button>
                  ) : summary.status === 'completed' ? (
                    <button 
                      className="btn-play"
                      onClick={() => setActiveVideoUrl(`http://localhost:9000/camera-summaries/${summary.summary_storage_path}`)}
                    >
                      ▶️ Play Summary
                    </button>
                  ) : (
                    <button className="btn-generate" disabled>
                      Processing...
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          
          {videos.length === 0 && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px' }}>
              <h3 style={{fontSize: '48px', margin: '0 0 15px 0'}}>📹</h3>
              <h3>No archived videos found</h3>
              <p>Record a video first to use the summarization feature.</p>
            </div>
          )}
        </div>
      )}

      {/* Video Modal */}
      {activeVideoUrl && (
        <div className="video-modal-overlay" onClick={() => setActiveVideoUrl(null)}>
          <div className="video-modal" onClick={e => e.stopPropagation()}>
            <button className="close-modal" onClick={() => setActiveVideoUrl(null)}>&times;</button>
            <video 
              src={activeVideoUrl} 
              className="summary-player" 
              controls 
              autoPlay 
            />
          </div>
        </div>
      )}
    </div>
    </DashboardLayout>
  );
};

export default Summarization;
