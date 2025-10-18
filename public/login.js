// Login page logic for Family Hub
// Handles authentication and secure token management

const API_BASE_URL = window.location.origin;

// DOM Elements
const loginForm = document.getElementById('loginForm');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const loginButton = document.getElementById('loginButton');
const loginButtonText = document.getElementById('loginButtonText');
const loginSpinner = document.getElementById('loginSpinner');
const alertBox = document.getElementById('alertBox');

// Show alert message
function showAlert(message, type = 'error') {
    alertBox.textContent = message;
    alertBox.className = `alert alert-${type} show`;

    // Auto-hide success messages after 3 seconds
    if (type === 'success') {
        setTimeout(() => {
            alertBox.classList.remove('show');
        }, 3000);
    }
}

// Hide alert message
function hideAlert() {
    alertBox.classList.remove('show');
}

// Set loading state
function setLoading(isLoading) {
    loginButton.disabled = isLoading;
    usernameInput.disabled = isLoading;
    passwordInput.disabled = isLoading;

    if (isLoading) {
        loginButtonText.style.display = 'none';
        loginSpinner.style.display = 'block';
    } else {
        loginButtonText.style.display = 'block';
        loginSpinner.style.display = 'none';
    }
}

// Login function
async function handleLogin(event) {
    event.preventDefault();
    hideAlert();

    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    // Validation
    if (!username || !password) {
        showAlert('Bitte fülle alle Felder aus', 'error');
        return;
    }

    setLoading(true);

    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include', // Important for cookies
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            // Handle specific error cases
            if (response.status === 429) {
                showAlert('Zu viele Login-Versuche. Bitte warte 15 Minuten.', 'error');
            } else if (response.status === 401) {
                showAlert('Benutzername oder Passwort falsch', 'error');
            } else {
                showAlert(data.detail || 'Login fehlgeschlagen', 'error');
            }
            setLoading(false);
            return;
        }

        // Login successful
        showAlert('Login erfolgreich! Weiterleitung...', 'success');

        // Store user info and token (fallback if cookies don't work)
        localStorage.setItem('user', JSON.stringify({
            username: data.user.username,
            email: data.user.email,
            is_admin: data.user.is_admin
        }));

        // Store access token as fallback for cookie issues
        localStorage.setItem('access_token', data.access_token);

        // Redirect to main app after short delay
        setTimeout(() => {
            window.location.href = '/index.html';
        }, 1000);

    } catch (error) {
        console.error('Login error:', error);
        showAlert('Verbindungsfehler. Bitte überprüfe deine Internetverbindung.', 'error');
        setLoading(false);
    }
}

// Check if already logged in
async function checkExistingSession() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
            credentials: 'include'
        });

        if (response.ok) {
            // User is already logged in, redirect to main app
            window.location.href = '/index.html';
        }
    } catch (error) {
        // Not logged in or error, stay on login page
        console.log('No existing session');
    }
}

// Event listeners
loginForm.addEventListener('submit', handleLogin);

// Check for existing session on page load
checkExistingSession();

// Allow Enter key in password field
passwordInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleLogin(e);
    }
});

// Focus username field on load
usernameInput.focus();
