import apiClient from './client';

export const cameraAPI = {
    // Fetch all registered cameras
    getAllCameras: async () => {
        return await apiClient('/camera', { method: 'GET' });
    },

    // Start video ingestion process
    startIngestion: async () => {
        return await apiClient('/ingestion/start', { method: 'GET' });
    },

    // Stop video ingestion process
    stopIngestion: async () => {
        return await apiClient('/ingestion/stop', { method: 'GET' });
    },
};
