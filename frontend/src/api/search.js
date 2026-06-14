import apiClient from './client';

// Simple in-memory cache for search query results to avoid redundant API hits
const queryCache = new Map();

export const searchAPI = {
    /**
     * Clear the search cache (e.g., if a new video is uploaded or deleted)
     */
    clearCache: () => {
        queryCache.clear();
    },

    uploadVideo: (formData) => {
        // Clear cache when new videos are uploaded as state might change
        queryCache.clear();
        return apiClient('/api/search/upload', {
            method: 'POST',
            body: formData,
        });
    },

    querySearch: (query, videoId, topK = 10, useLlm = true, options = {}) => {
        const cacheKey = `${videoId}_${query}_${topK}_${useLlm}`;
        
        // Return cached result if it exists and cache is not bypassed
        if (!options.bypassCache && queryCache.has(cacheKey)) {
            console.log(`[Cache Hit] Returning cached results for query: "${query}"`);
            return Promise.resolve(queryCache.get(cacheKey));
        }

        const timeoutMs = options.timeoutMs || 180000; // default 3 minute timeout
        const controller = options.controller || new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
        
        return apiClient('/api/search/query', {
            method: 'POST',
            signal: controller.signal,
            body: JSON.stringify({
                video_id: videoId,
                query: query,
                top_k: topK,
                use_llm: useLlm,
            }),
        })
        .then(data => {
            // Cache successful queries
            queryCache.set(cacheKey, data);
            return data;
        })
        .finally(() => clearTimeout(timeoutId));
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

    getVideoFrames: (videoId) => {
        return apiClient(`/api/search/video/${videoId}/frames`, {
            method: 'GET',
        });
    },

    /**
     * Helper to poll video indexing status until it's completed or failed
     */
    pollVideoStatus: (videoId, onProgress, interval = 3000, maxRetries = 100) => {
        let retries = 0;
        return new Promise((resolve, reject) => {
            const check = setInterval(async () => {
                try {
                    const statusData = await searchAPI.getVideoStatus(videoId);
                    retries++;
                    
                    if (onProgress) onProgress(statusData);

                    if (statusData.status === 'completed') {
                        clearInterval(check);
                        resolve(statusData);
                    } else if (statusData.status === 'failed') {
                        clearInterval(check);
                        reject(new Error("Video indexing task failed on backend."));
                    } else if (retries >= maxRetries) {
                        clearInterval(check);
                        reject(new Error("Video indexing status polling timed out."));
                    }
                } catch (err) {
                    clearInterval(check);
                    reject(err);
                }
            }, interval);
        });
    },

    deleteVideo: (videoId) => {
        // Clear cache to keep video state synchronized
        queryCache.clear();
        return apiClient(`/api/search/video/${videoId}`, {
            method: 'DELETE',
        });
    },

    startRecording: (cameraId, duration = 600, chunkSize = 300, burnBboxes = false) => {
        return apiClient(`/api/search/record/${cameraId}`, {
            method: 'POST',
            body: JSON.stringify({
                duration: duration,
                chunk_size: chunkSize,
                sampling_rate: 16,
                burn_bboxes: burnBboxes
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
    },

    getActiveRecordings: () => {
        return apiClient('/api/search/record/active', {
            method: 'GET',
        });
    },

    /**
     * Helper to poll active recording status until completed, failed or stopped
     */
    pollRecordingStatus: (cameraId, onUpdate, interval = 3000, maxRetries = 200) => {
        let retries = 0;
        return new Promise((resolve, reject) => {
            const check = setInterval(async () => {
                try {
                    const data = await searchAPI.getRecordingStatus(cameraId);
                    retries++;
                    
                    if (onUpdate) onUpdate(data);

                    if (data.status === 'completed' || data.status === 'not_found') {
                        clearInterval(check);
                        resolve(data);
                    } else if (data.status === 'failed') {
                        clearInterval(check);
                        reject(new Error(data.error || "Recording failed on backend."));
                    } else if (retries >= maxRetries) {
                        clearInterval(check);
                        reject(new Error("Recording status polling timed out."));
                    }
                } catch (err) {
                    clearInterval(check);
                    reject(err);
                }
            }, interval);
        });
    }
};
