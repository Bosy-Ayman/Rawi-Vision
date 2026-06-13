import React, { useState, useEffect, useRef, useCallback } from 'react';
import { summarizationApi } from '../api/summarization';
import { searchAPI } from '../api/search';
import ToastNotification from '../components/modals/ToastNotification';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import './Summarization.css';

const STAGE_LABELS = {
  downloading:       'Downloading video…',
  loading_model:     'Loading AI model…',
  scanning_frames:   'Scanning frames for motion…',
  detecting_objects: 'Running object detection…',
  uploading:         'Uploading summary…',
  completed:         'Done!',
  failed:            'Failed',
  pending:           'Queued…',
};

const Summarization = () => {
  const [videos, setVideos]           = useState([]);
  const [summaries, setSummaries]     = useState({});
  const [progress, setProgress]       = useState({}); // { [summary_id]: { percent, stage } }
  const [autoSummarize, setAutoSummarize] = useState(false);
  const [loading, setLoading]         = useState(true);
  const [activeVideo, setActiveVideo] = useState(null); // { url, title }
  const [notification, setNotification] = useState(null);
  const pollTimers = useRef({});

  const showToast = (type, title, message) => {
    setNotification({ type, title, message });
    setTimeout(() => setNotification(null), 5000);
  };

  /* ---------- presigned URL fetcher (kept for fallback) ---------- */
  const fetchVideoUrl = useCallback(async (summaryId) => {
    try {
      const data = await summarizationApi.getVideoUrl(summaryId);
      return data?.url || null;
    } catch (_) { return null; }
  }, []);

  /* ---------- polling ---------- */
  const startPolling = useCallback((summaryId) => {
    if (pollTimers.current[summaryId]) return;           // already polling
    pollTimers.current[summaryId] = setInterval(async () => {
      try {
        const data = await summarizationApi.getProgress(summaryId);
        setProgress(prev => ({ ...prev, [summaryId]: data }));

        if (data.stage === 'completed' || data.stage === 'failed') {
          clearInterval(pollTimers.current[summaryId]);
          delete pollTimers.current[summaryId];
          // Refresh summaries list so status badge + Play button appear
          const sumsList = await summarizationApi.listSummaries();
          const sumsMap = {};
          (sumsList || []).forEach(s => { sumsMap[s.video_id] = s; });
          setSummaries(sumsMap);
        }
      } catch (_) { /* swallow */ }
    }, 2000);
  }, [fetchVideoUrl]);

  const stopAllPolling = () => {
    Object.values(pollTimers.current).forEach(clearInterval);
    pollTimers.current = {};
  };

  /* ---------- initial data ---------- */
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [settings, vids, sumsList] = await Promise.all([
        summarizationApi.getAutoSettings(),
        searchAPI.listVideos(),
        summarizationApi.listSummaries(),
      ]);
      setAutoSummarize(settings.auto_summarize);
      setVideos(vids || []);

      const sumsMap = {};
      (sumsList || []).forEach(s => { sumsMap[s.video_id] = s; });
      setSummaries(sumsMap);

      // Auto-start polling for any in-progress tasks
      (sumsList || []).filter(s => s.status === 'processing' || s.status === 'pending')
                      .forEach(s => startPolling(s.id));
    } catch (error) {
      showToast('error', 'Error', 'Failed to load summarization data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [startPolling]);

  useEffect(() => {
    fetchData();
    return stopAllPolling;  // cleanup on unmount
  }, [fetchData]);

  /* ---------- handlers ---------- */
  const handleToggleAuto = async () => {
    const newValue = !autoSummarize;
    setAutoSummarize(newValue);
    try {
      await summarizationApi.updateAutoSettings(newValue);
      showToast('success', 'Settings Updated', `Auto-Summarize turned ${newValue ? 'ON' : 'OFF'}`);
    } catch {
      setAutoSummarize(!newValue);
      showToast('error', 'Error', 'Failed to update setting');
    }
  };

  const handleGenerate = async (video) => {
    try {
      showToast('info', 'Generating', 'Triggering summarization…');
      const newSummary = await summarizationApi.generateSummary(
        video.video_id, video.camera_id, video.storage_path
      );
      setSummaries(prev => ({ ...prev, [video.video_id]: newSummary }));
      setProgress(prev => ({ ...prev, [newSummary.id]: { percent: 0, stage: 'pending' } }));
      startPolling(newSummary.id);
      showToast('success', 'Started', 'Summarization task started!');
    } catch (error) {
      showToast('error', 'Error', error?.detail || 'Failed to trigger summarization');
    }
  };

  const getStatusClass = (status) => {
    switch (status) {
      case 'completed':  return 'status-completed';
      case 'failed':     return 'status-failed';
      case 'processing': return 'status-processing';
      default:           return 'status-pending';
    }
  };

  /* ---------- render ---------- */
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

        {/* Header */}
        <div className="summarization-header">
          <p style={{ margin: 0, color: '#64748b', fontSize: '1rem' }}>
            Condense hours of footage into minutes using AI.&nbsp;
            Summaries are stored in MinIO under the <code>camera-summaries</code> bucket.
          </p>
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

        {/* Grid */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '50px', color: '#64748b' }}>Loading…</div>
        ) : (
          <div className="video-grid">
            {videos.map(video => {
              const summary = summaries[video.video_id];
              const prog    = summary ? progress[summary.id] : null;
              const pct     = prog?.percent ?? 0;
              const stage   = prog?.stage   ?? summary?.status ?? 'pending';
              const isProcessing = summary && (summary.status === 'processing' || summary.status === 'pending');
              // Direct public URL — camera-summaries bucket has public-read policy
              const videoUrl = (summary?.status === 'completed' && summary?.summary_storage_path)
                ? `http://localhost:9000/camera-summaries/${summary.summary_storage_path}`
                : null;

              return (
                <div key={video.video_id} className="video-card">
                  {/* Card header */}
                  <div className="card-header-row">
                    <h3 className="card-title">{video.filename}</h3>
                    {summary && (
                      <span className={`status-badge ${getStatusClass(summary.status)}`}>
                        {summary.status.toUpperCase()}
                      </span>
                    )}
                  </div>

                  {/* Meta */}
                  <p className="card-meta">
                    📷 Camera: <span>{video.camera_room || video.camera_id}</span>
                  </p>
                  <p className="card-meta storage-path">
                    🗂 Source: <code>{video.storage_path}</code>
                  </p>
                  {summary?.summary_storage_path && (
                    <p className="card-meta storage-path">
                      ✅ Summary: <code>camera-summaries/{summary.summary_storage_path}</code>
                    </p>
                  )}

                  {/* Progress bar */}
                  {isProcessing && (
                    <div className="progress-wrapper">
                      <div className="progress-label">
                        <span>{STAGE_LABELS[stage] || stage}</span>
                        <span className="progress-pct">{pct}%</span>
                      </div>
                      <div className="progress-track">
                        <div
                          className="progress-fill"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Inline video player */}
                  {videoUrl && (
                    <div className="inline-player">
                      <video
                        src={videoUrl}
                        controls
                        className="summary-player-inline"
                        title={`Summary of ${video.filename}`}
                      />
                      <p className="player-caption">🎬 AI Summary Video</p>
                    </div>
                  )}

                  {/* Action button */}
                  <div className="card-actions">
                    {!summary || summary.status === 'failed' ? (
                      <button className="btn-generate" onClick={() => handleGenerate(video)}>
                        ⚙️ Generate Summary
                      </button>
                    ) : summary.status === 'completed' ? (
                      <button
                        className="btn-play"
                        onClick={() => setActiveVideo({ url: videoUrl, title: video.filename })}
                      >
                        ⛶ Full-screen
                      </button>
                    ) : (
                      <button className="btn-generate" disabled>
                        ⏳ {STAGE_LABELS[stage] || 'Processing…'}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {videos.length === 0 && (
              <div className="empty-state">
                <h3>📹</h3>
                <h4>No archived videos found</h4>
                <p>Record a video first to use the summarization feature.</p>
              </div>
            )}
          </div>
        )}

        {/* Full-screen modal */}
        {activeVideo && (
          <div className="video-modal-overlay" onClick={() => setActiveVideo(null)}>
            <div className="video-modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h3>🎬 {activeVideo.title}</h3>
                <button className="close-modal" onClick={() => setActiveVideo(null)}>&times;</button>
              </div>
              <video
                src={activeVideo.url}
                className="summary-player"
                controls
                autoPlay
              />
              <p className="modal-caption">
                Stored in MinIO → <code>camera-summaries</code>
              </p>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default Summarization;
