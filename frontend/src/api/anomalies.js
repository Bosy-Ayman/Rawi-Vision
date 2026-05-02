// frontend/src/api/anomalies.js
import apiClient from './client';

export const anomalyAPI = {
    // Fetch the 50 most recent anomalies
    getAnomalies: async () => {
        return await apiClient('/anomalies/');
    },

    // Fetch a single anomaly by ID
    getAnomalyById: async (id) => {
        return await apiClient(`/anomalies/${id}`);
    },

    startAnomaly: async () => {
        return await apiClient('/anomalies/start');
    },

    stopAnomaly: async () => {
        return await apiClient('/anomalies/stop');
    },
};
