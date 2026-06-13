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

    deleteAnomaly: async (id) => {
        return await apiClient(`/anomalies/remove-anomaly/${id}`, {
            method: 'DELETE'
        });
    },

    bulkDelete: async (ids) => {
        return await apiClient(`/anomalies/bulk-remove`, {
            method: 'POST',
            body: JSON.stringify({ ids })
        });
    },

    deleteAll: async () => {
        return await apiClient(`/anomalies/remove-all`, {
            method: 'DELETE'
        });
    },

    startAnomaly: async () => {
        return await apiClient('/anomalies/start');
    },

    stopAnomaly: async () => {
        return await apiClient('/anomalies/stop');
    },
};
