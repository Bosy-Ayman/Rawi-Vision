// frontend/src/api/auth.js
import apiClient from './client';

export const authAPI = {
    // Login with Google token
    loginWithGoogle: async (idToken) => {
        return await apiClient('/auth/google', {
            method: 'POST',
            body: JSON.stringify({ id_token: idToken })
        });
    },

    // Get all system users (SuperAdmin only)
    getSystemUsers: async () => {
        return await apiClient('/auth/users', {
            method: 'GET'
        });
    },

    // Add a new system user (SuperAdmin only)
    addSystemUser: async (userData) => {
        return await apiClient('/auth/users', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    },

    // Remove a system user (SuperAdmin only)
    removeSystemUser: async (email) => {
        return await apiClient(`/auth/users/${encodeURIComponent(email)}`, {
            method: 'DELETE'
        });
    },

    // Logout to clear the HttpOnly refresh token
    logout: async () => {
        return await apiClient('/auth/logout', {
            method: 'POST'
        });
    }
};
