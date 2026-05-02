// frontend/src/api/camera.js
import apiClient from './client';

export const cameraAPI = {
    // Get all cameras
    getAllCameras: async () => {
        return await apiClient('/camera', {
            method: 'GET'
        });
    },

    // Discover online cameras
    discoverCameras: async () => {
        return await apiClient('/camera_discovery/discovery', {
            method: 'GET'
        });
    },

    // Create a new camera
    createCamera: async (formData) => {
        // formData is passed directly. fetch automatically sets multipart/form-data.
        return await apiClient('/camera', {
            method: 'POST',
            body: formData
        });
    },

    // Delete a camera
    deleteCamera: async (id) => {
        return await apiClient(`/camera/${id}`, {
            method: 'DELETE'
        });
    }
};
