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
  }
};
