// frontend/src/api/client.js
// A central API client that automatically handles the base URL and auth tokens

const BASE_URL = 'http://127.0.0.1:8000';

async function apiClient(endpoint, options = {}) {
    // Merge default options
    const customConfig = {
        ...options,
        headers: {
            ...options.headers,
        },
    };

    // Auto-attach the JWT token if we have one saved in localStorage
    const token = localStorage.getItem('access_token');
    if (token) {
        customConfig.headers['Authorization'] = `Bearer ${token}`;
    }

    // Default to JSON if we're sending a body and haven't explicitly set another Content-Type
    if (customConfig.body && !(customConfig.body instanceof FormData) && !customConfig.headers['Content-Type']) {
        customConfig.headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, customConfig);

    // Attempt to parse JSON response
    let data;
    try {
        data = await response.json();
    } catch (err) {
        data = null;
    }

    if (response.ok) {
        return data;
    }

    // --- INTERCEPTOR LOGIC FOR 401 UNAUTHORIZED ---
    // If the access token is expired, the backend returns 401.
    // We catch it here, try to refresh silently using the HttpOnly cookie,
    // and if successful, replay the original request.
    if (response.status === 401 && endpoint !== '/auth/refresh' && endpoint !== '/auth/google') {
        try {
            // Attempt to refresh the token using the HttpOnly cookie
            const refreshResponse = await fetch(`${BASE_URL}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include' // THIS IS CRUCIAL: Sends the HttpOnly cookie
            });

            if (refreshResponse.ok) {
                const refreshData = await refreshResponse.json();

                // Save the brand new 15-minute access token
                localStorage.setItem('access_token', refreshData.access_token);

                // Replay the original failed request with the new token
                customConfig.headers['Authorization'] = `Bearer ${refreshData.access_token}`;
                const retryResponse = await fetch(`${BASE_URL}${endpoint}`, customConfig);

                let retryData;
                try { retryData = await retryResponse.json(); } catch (e) { retryData = null; }

                if (retryResponse.ok) {
                    return retryData;
                }
                return Promise.reject(retryData || { detail: 'Unexpected error on retry' });
            }
        } catch (refreshErr) {
            console.error("Silent refresh failed", refreshErr);
        }

        // If we reach here, the refresh token itself is expired or missing.
        // We must log the user out fully.
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_role');
        localStorage.removeItem('full_name');
        window.location.href = '/'; // Force redirect to login page
        return Promise.reject({ detail: 'Session expired. Please log in again.' });
    }

    // Reject with a standardized error object
    return Promise.reject(data || { detail: 'An unexpected error occurred' });
}

export default apiClient;
