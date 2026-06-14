import React, { useState, useEffect, useRef, useCallback } from 'react';
import { summarizationApi } from '../api/summarization';
import { searchAPI } from '../api/search';
import { BASE_URL } from '../api/client';
import ToastNotification from '../components/modals/ToastNotification';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import './Summarization.css';

const STAGE_LABELS = {
  downloading:       'Downloading video…',
  loading_model:     'Loading AI model…',
  scanning_frames:   'Scanning frames…',
  detecting_objects: 'Detecting objects…',
  uploading:         'Uploading…',
  completed:         'Complete',
  failed:            'Failed',
  pending:           'Queued',
};

const Summarization = () => {
  const [videos, setVideos]             = useState([]);
  const [summaries, setSummaries]       = useState({}); // { video_id → best summary }
  const [progress, setProgress]         = useState({}); // { summary_id → { percent, stage } }
  const [autoSummarize, setAutoSummarize] = useState(false);
  const [loading, setLoading]           = useState(true);
  const [activeVideo, setActiveVideo]   = useState(null); // { url, title }
  const [notification, setNotification] = useState(null);
  const [searchQuery, setSearchQuery]   = useState('');
  const pollTimers = useRef({});

  const showToast = (type, title, message) => {
    setNotification({ type, title, message });
    setTimeout(() => setNotification(null), 5000);
  };

  /* ---------- polling ---------- */
  const startPolling = useCallback((summaryId) => {
    if (pollTimers.current[summaryId]) return;
    pollTimers.current[summaryId] = setInterval(async () => {
      try {
        const data = await summarizationApi.getProgress(summaryId);
        setProgress(prev => ({ ...prev, [summaryId]: data }));
        if (data.stage === 'completed' || data.stage === 'failed') {
          clearInterval(pollTimers.current[summaryId]);
          delete pollTimers.current[summaryId];
          const sumsList = await summarizationApi.listSummaries();
          setSummaries(buildSummaryMap(sumsList));
        }
      } catch (_) { /* swallow */ }
    }, 2000);
  }, []);

  const stopAllPolling = () => {
    Object.values(pollTimers.current).forEach(clearInterval);
    pollTimers.current = {};
  };

  /* Pick the best summary per video:
     prefer completed > processing/pending > failed (most recent wins within tier) */
  const buildSummaryMap = (list) => {
    const tierOf = s => s.status === 'completed' ? 0 : (s.status === 'failed' ? 2 : 1);
    const map = {};
    (list || []).forEach(s => {
      const existing = map[s.video_id];
      if (!existing) { map[s.video_id] = s; return; }
      const t = tierOf(s), te = tierOf(existing);
      if (t < te || (t === te && s.date_created > existing.date_created)) {
        map[s.video_id] = s;
      }
    });
    return map;
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
      setSummaries(buildSummaryMap(sumsList));
      (sumsList || [])
        .filter(s => s.status === 'processing' || s.status === 'pending')
        .forEach(s => startPolling(s.id));
    } catch (err) {
      showToast('error', 'Error', 'Failed to load data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [startPolling]);

  useEffect(() => { fetchData(); return stopAllPolling; }, [fetchData]);

  /* ---------- handlers ---------- */
  const handleToggleAuto = async () => {
    const next = !autoSummarize;
    setAutoSummarize(next);
    try {
      await summarizationApi.updateAutoSettings(next);
      showToast('success', 'Updated', `Auto-Summarize ${next ? 'ON' : 'OFF'}`);
    } catch {
      setAutoSummarize(!next);
      showToast('error', 'Error', 'Failed to update setting');
    }
  };

  const handleGenerate = async (video) => {
    try {
      showToast('info', 'Starting…', 'Queuing summarization task');
      const newSummary = await summarizationApi.generateSummary(
        video.video_id, video.camera_id, video.storage_path
      );
      setSummaries(prev => ({ ...prev, [video.video_id]: newSummary }));
      setProgress(prev => ({ ...prev, [newSummary.id]: { percent: 0, stage: 'pending' } }));
      startPolling(newSummary.id);
      showToast('success', 'Started', 'Summarization task queued!');
    } catch (err) {
      showToast('error', 'Error', err?.detail || 'Failed to start summarization');
    }
  };

  const handleDeleteSummary = async (summaryId, videoId) => {
    if (!window.confirm("Are you sure you want to delete this summary?")) return;
    try {
      await summarizationApi.deleteSummary(summaryId);
      setSummaries(prev => {
        const next = { ...prev };
        delete next[videoId];
        return next;
      });
      showToast('success', 'Deleted', 'Summary was successfully deleted.');
    } catch (err) {
      showToast('error', 'Error', err?.detail || 'Failed to delete summary');
    }
  };

  const handleDeleteVideo = async (videoId) => {
    if (!window.confirm("Are you sure you want to delete this original video? This action is permanent.")) return;
    try {
      await searchAPI.deleteVideo(videoId);
      setVideos(prev => prev.filter(v => v.video_id !== videoId));
      showToast('success', 'Deleted', 'Original video deleted.');
    } catch (err) {
      showToast('error', 'Error', err?.detail || 'Failed to delete video');
    }
  };

  const statusClass = s => ({ completed: 'status-completed', failed: 'status-failed', processing: 'status-processing' }[s] || 'status-pending');

  /* ---------- render ---------- */
  return (
    <DashboardLayout title="Video Summarization">
      <div className="sum-page">

        {notification && (
          <ToastNotification
            type={notification.type}
            title={notification.title}
            message={notification.message}
            onClose={() => setNotification(null)}
          />
        )}

        {/* ── Header ─────────────────────────────── */}
        <div className="sum-header">
          <div className="sum-header-left">
            <h1 className="sum-title">
              <span className="sum-title-icon">🎬</span>
              Video Summarization
            </h1>
            <p className="sum-subtitle">
              AI condenses hours of footage into concise highlight reels
            </p>
          </div>
          
          <div className="sum-header-search">
            <div className="search-input-wrapper">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                placeholder="Search videos..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="sum-search-input"
                style={{
                  padding: '8px 12px 8px 32px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  backgroundColor: 'var(--bg-card)',
                  color: 'var(--text-primary)',
                  width: '100%',
                  minWidth: '200px'
                }}
              />
            </div>
          </div>
          <div className="sum-auto-toggle">
            <div className="toggle-label-group">
              <span className="toggle-title">Auto-Summarize</span>
              <span className="toggle-sub">New recordings</span>
            </div>
            <label className="toggle-pill">
              <input
                type="checkbox"
                checked={autoSummarize}
                onChange={handleToggleAuto}
                disabled={loading}
              />
              <span className="toggle-track">
                <span className="toggle-thumb" />
              </span>
            </label>
          </div>
        </div>

        {/* ── Grid ───────────────────────────────── */}
        {loading ? (
          <div className="sum-loading">
            <div className="sum-spinner" />
            <p>Loading videos…</p>
          </div>
        ) : videos.length === 0 ? (
          <div className="sum-empty">
            <div className="sum-empty-icon">📹</div>
            <h3>No archived videos</h3>
            <p>Record a video stream first — it will appear here for summarization.</p>
          </div>
        ) : (
          <div className="sum-grid">
            {videos.filter(v => {
              const query = searchQuery.toLowerCase();
              const summary = summaries[v.video_id];
              const status = summary ? summary.status.toLowerCase() : 'unsummarized';
              
              return (v.filename || '').toLowerCase().includes(query) ||
                     (v.camera_room || '').toLowerCase().includes(query) ||
                     (v.camera_number || '').toLowerCase().includes(query) ||
                     status.includes(query);
            }).map(video => {
              const summary     = summaries[video.video_id];
              const prog        = summary ? progress[summary.id] : null;
              const pct         = prog?.percent ?? 0;
              const stage       = prog?.stage ?? summary?.status ?? 'none';
              const isActive    = summary && (summary.status === 'processing' || summary.status === 'pending');
              const isCompleted = summary?.status === 'completed' && summary?.summary_storage_path;
              const videoUrl    = isCompleted
                ? `${BASE_URL}/api/summarization/video/${summary.id}/stream`
                : null;

              return (
                <div key={video.video_id} className={`sum-card ${isCompleted ? 'sum-card--done' : ''}`}>

                  {/* Status chip */}
                  {summary && (
                    <span className={`sum-chip ${statusClass(summary.status)}`}>
                      {summary.status === 'completed' ? '✓ Done'
                        : summary.status === 'processing' ? '⚙ Processing'
                        : summary.status === 'pending'    ? '⏳ Queued'
                        : '✕ Failed'}
                    </span>
                  )}

                  {/* Inline video OR placeholder */}
                  <div className="sum-card-media">
                    {videoUrl ? (
                      <video
                        key={videoUrl}
                        src={videoUrl}
                        className="sum-video"
                        controls
                        preload="metadata"
                      />
                    ) : (
                      <div className="sum-media-placeholder">
                        {isActive ? (
                          <>
                            <div className="sum-spinner-sm" />
                            <span>Processing…</span>
                          </>
                        ) : (
                          <>
                            <span className="placeholder-icon">🎞</span>
                            <span>No summary yet</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Progress bar */}
                  {isActive && (
                    <div className="sum-progress">
                      <div className="sum-progress-info">
                        <span className="sum-progress-stage">{STAGE_LABELS[stage] || stage}</span>
                        <span className="sum-progress-pct">{pct}%</span>
                      </div>
                      <div className="sum-progress-track">
                        <div className="sum-progress-fill" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )}

                  {/* Info */}
                  <div className="sum-card-info">
                    <p className="sum-card-name" title={video.filename}>{video.filename}</p>
                    <p className="sum-card-meta">
                      <span className="meta-icon">📷</span>
                      {video.camera_room || 'Camera'} · {video.camera_number || ''}
                    </p>
                    {isCompleted && (
                      <p className="sum-card-path">
                        <span className="meta-icon">🗂</span>
                        <code>camera-summaries/{summary.summary_storage_path}</code>
                      </p>
                    )}
                  </div>

                  <div className="sum-card-actions">
                    {!summary || summary.status === 'failed' ? (
                      <div style={{ display: 'flex', gap: '8px', width: '100%' }}>
                        <button className="sum-btn sum-btn--primary" style={{ flex: 1 }} onClick={() => handleGenerate(video)}>
                          <span>⚙</span> Generate
                        </button>
                        <button
                          className="sum-btn sum-btn--watch"
                          style={{ flex: 1 }}
                          onClick={() => setActiveVideo({ url: `${BASE_URL}/api/search/video/${video.video_id}/stream`, title: video.filename })}
                        >
                          <span>▶</span> Play
                        </button>
                        <button
                          className="sum-btn"
                          style={{ backgroundColor: 'var(--bg-card-hover)', color: 'var(--text-secondary)', padding: '0 12px' }}
                          onClick={() => handleDeleteVideo(video.video_id)}
                          title="Delete Video"
                        >
                          <span>🗑️</span>
                        </button>
                      </div>
                    ) : isCompleted ? (
                      <div style={{ display: 'flex', gap: '8px', width: '100%' }}>
                        <button
                          className="sum-btn sum-btn--watch"
                          style={{ flex: 1 }}
                          onClick={() => setActiveVideo({ url: videoUrl, title: video.filename })}
                        >
                          <span>⛶</span> Summary
                        </button>
                        <button
                          className="sum-btn sum-btn--watch"
                          style={{ flex: 1 }}
                          onClick={() => setActiveVideo({ url: `${BASE_URL}/api/search/video/${video.video_id}/stream`, title: video.filename })}
                        >
                          <span>▶</span> Original
                        </button>
                        <button
                          className="sum-btn"
                          style={{ backgroundColor: 'var(--bg-card-hover)', color: 'var(--text-secondary)', padding: '0 12px' }}
                          onClick={() => handleDeleteVideo(video.video_id)}
                          title="Delete Video"
                        >
                          <span>🗑️</span>
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '8px', width: '100%' }}>
                        <button className="sum-btn sum-btn--disabled" style={{ flex: 1 }} disabled>
                          <span>⏳</span> {STAGE_LABELS[stage] || 'Working…'}
                        </button>
                        <button
                          className="sum-btn"
                          style={{ backgroundColor: 'var(--bg-card-hover)', color: 'var(--text-secondary)', padding: '0 12px' }}
                          onClick={() => handleDeleteVideo(video.video_id)}
                          title="Delete Video"
                        >
                          <span>🗑️</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Full-screen modal ──────────────────── */}
        {activeVideo && (
          <div className="sum-modal-backdrop" onClick={() => setActiveVideo(null)}>
            <div className="sum-modal" onClick={e => e.stopPropagation()}>
              <div className="sum-modal-header">
                <div className="sum-modal-title">
                  <span>🎬</span>
                  <span>{activeVideo.title}</span>
                </div>
                <button className="sum-modal-close" onClick={() => setActiveVideo(null)}>✕</button>
              </div>
              <div className="sum-modal-body">
                <video
                  key={activeVideo.url}
                  src={activeVideo.url}
                  className="sum-modal-video"
                  controls
                  preload="auto"
                  playsInline
                  autoPlay
                />
              </div>
              <p className="sum-modal-footer">
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
