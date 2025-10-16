// Authentication utilities for Family Hub frontend
// Handles session management, token refresh, and auth checks

const API_BASE_URL = window.location.origin;

// Authentication utility object
const AuthUtils = {
    // Check if user is authenticated
    async isAuthenticated() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
                credentials: 'include'
            });
            return response.ok;
        } catch (error) {
            console.error('Auth check error:', error);
            return false;
        }
    },

    // Get current user info
    async getCurrentUser() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
                credentials: 'include'
            });

            if (!response.ok) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('Get user error:', error);
            return null;
        }
    },

    // Refresh access token
    async refreshToken() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
                method: 'POST',
                credentials: 'include'
            });

            return response.ok;
        } catch (error) {
            console.error('Token refresh error:', error);
            return false;
        }
    },

    // Logout user
    async logout() {
        try {
            await fetch(`${API_BASE_URL}/api/auth/logout`, {
                method: 'POST',
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            // Clear local storage
            localStorage.removeItem('user');
            // Redirect to login
            window.location.href = '/login.html';
        }
    },

    // Redirect to login if not authenticated
    async requireAuth() {
        const isAuth = await this.isAuthenticated();
        if (!isAuth) {
            // Save current page to redirect back after login
            localStorage.setItem('redirectAfterLogin', window.location.pathname);
            window.location.href = '/login.html';
            return false;
        }
        return true;
    },

    // Make authenticated API request with automatic token refresh
    async authenticatedFetch(url, options = {}) {
        // Ensure credentials are included
        options.credentials = 'include';

        let response = await fetch(url, options);

        // If unauthorized, try to refresh token
        if (response.status === 401) {
            const refreshed = await this.refreshToken();

            if (refreshed) {
                // Retry request with new token
                response = await fetch(url, options);
            } else {
                // Refresh failed, redirect to login
                this.logout();
                throw new Error('Authentication failed');
            }
        }

        return response;
    },

    // Get user from localStorage (cached)
    getCachedUser() {
        const userStr = localStorage.getItem('user');
        if (userStr) {
            try {
                return JSON.parse(userStr);
            } catch {
                return null;
            }
        }
        return null;
    },

    // Setup periodic token refresh (every 25 minutes)
    setupTokenRefresh() {
        // Refresh token every 25 minutes (access token expires after 30)
        setInterval(async () => {
            const isAuth = await this.isAuthenticated();
            if (isAuth) {
                await this.refreshToken();
                console.log('Token refreshed automatically');
            }
        }, 25 * 60 * 1000); // 25 minutes
    }
};

// Make AuthUtils available globally
window.AuthUtils = AuthUtils;

// Auto-setup token refresh when module loads
AuthUtils.setupTokenRefresh();
