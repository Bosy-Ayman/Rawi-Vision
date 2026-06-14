import apiClient from './client';

export const summarizationApi = {
  // Generate summary for a video manually
  generateSummary: async (videoId, cameraId, storagePath) => {
    return apiClient(`/api/summarization/generate/${videoId}?camera_id=${cameraId}&storage_path=${encodeURIComponent(storagePath)}`, {
      method: 'POST'
    });
  },

  // List all summaries
  listSummaries: async () => {
    return apiClient('/api/summarization/list', {
      method: 'GET'
    });
  },

  // Delete a summary
  deleteSummary: async (summaryId) => {
    return apiClient(`/api/summarization/${summaryId}`, {
      method: 'DELETE'
    });
  },

  // Get auto-summarize settings
  getAutoSettings: async () => {
    return apiClient('/api/summarization/settings/auto', {
      method: 'GET'
    });
  },

  // Update auto-summarize settings
  updateAutoSettings: async (autoSummarize) => {
    return apiClient('/api/summarization/settings/auto', {
      method: 'POST',
      body: JSON.stringify({ auto_summarize: autoSummarize })
    });
  },

  // Get live progress for a running task
  getProgress: async (summaryId) => {
    return apiClient(`/api/summarization/progress/${summaryId}`, { method: 'GET' });
  },

  // Get a presigned URL for playing the completed summary video
  getVideoUrl: async (summaryId) => {
    return apiClient(`/api/summarization/video-url/${summaryId}`, { method: 'GET' });
  }
};

