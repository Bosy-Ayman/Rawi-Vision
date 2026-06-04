import apiClient from './client';

export const searchAPI = {
    uploadVideo: (formData) => {
        // We use fetch directly here or pass formData properly so apiClient doesn't overwrite headers
        return apiClient('/api/search/upload', {
            method: 'POST',
            body: formData,
        });
    },

    querySearch: (query, videoId, topK = 10, useLlm = true) => {
        return apiClient('/api/search/query', {
            method: 'POST',
            body: JSON.stringify({
                video_id: videoId,
                query: query,
                top_k: topK,
                use_llm: useLlm,
            }),
        });
    },

    listVideos: () => {
        return apiClient('/api/search/videos', {
            method: 'GET',
        });
    },

    getVideoStatus: (videoId) => {
        return apiClient(`/api/search/status/${videoId}`, {
            method: 'GET',
        });
    },

    deleteVideo: (videoId) => {
        return apiClient(`/api/search/video/${videoId}`, {
            method: 'DELETE',
        });
    },

    startRecording: (cameraId, duration = 600, chunkSize = 300) => {
        return apiClient(`/api/search/record/${cameraId}`, {
            method: 'POST',
            body: JSON.stringify({
                duration: duration,
                chunk_size: chunkSize,
                sampling_rate: 16
            })
        });
    },

    stopRecording: (cameraId) => {
        return apiClient(`/api/search/record/${cameraId}/stop`, {
            method: 'POST',
        });
    },

    getRecordingStatus: (cameraId) => {
        return apiClient(`/api/search/record/${cameraId}/status`, {
            method: 'GET',
        });
    }
};
