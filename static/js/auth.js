/*
 * =========================================
 * CORELYTICS - AUTHENTICATION SCRIPT
 * =========================================
 * This file handles Google Sign-In callbacks and
 * toast messages for the login and signup pages.
 */

/**
 * Handles the response from Google Sign-In.
 * This function is called by the Google GSI client.
 * @param {object} response - The credential response object from Google.
 */
function handleCredentialResponse(response) {
    const id_token = response.credential;
    
    // Show loading/processing toast
    showAuthMessage('Verifying your Google account...', 'info');

    fetch('/google-signup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ id_token: id_token })
    })
    .then((response) => response.json())
    .then((data) => {
        if (data.success) {
            showAuthMessage(data.message || 'Login successful! Redirecting...', 'success');
            // Redirect based on backend response
            setTimeout(() => {
                if (data.redirect_to_onboarding) {
                    window.location.href = '/onboarding';
                } else {
                    window.location.href = '/dashboard';
                }
            }, 1500); // Wait 1.5s for user to see success message
        } else {
            showAuthMessage(data.message || 'Google Sign-In failed.', 'error');
        }
    })
    .catch((error) => {
        console.error('Error sending ID token to backend:', error);
        showAuthMessage('An error occurred during Google Sign-In.', 'error');
    });
}

/**
 * Displays a toast message on the auth pages.
 * @param {string} message - The text to display.
 * @param {string} type - 'info', 'success', or 'error' (or 'danger').
 */
function showAuthMessage(message, type = 'info') {
    const toastMessageBox = document.getElementById('toastMessageBox');
    if (!toastMessageBox) {
        console.error('toastMessageBox element not found');
        return;
    }

    toastMessageBox.textContent = message;
    // Reset classes
    toastMessageBox.classList.remove('success', 'error', 'info', 'show');

    // Add type class
    if (type === 'success') {
        toastMessageBox.classList.add('success');
    } else if (type === 'error' || type === 'danger') {
        toastMessageBox.classList.add('error');
    } else {
        toastMessageBox.classList.add('info');
    }

    // Show toast
    toastMessageBox.classList.add('show');

    // Clear existing timeout
    if (toastMessageBox.timeoutId) {
        clearTimeout(toastMessageBox.timeoutId);
    }

    // Hide after 3 seconds
    toastMessageBox.timeoutId = setTimeout(() => {
        toastMessageBox.classList.remove('show');
        // Clear text after transition
        setTimeout(() => {
            if (!toastMessageBox.classList.contains('show')) {
                toastMessageBox.textContent = '';
            }
        }, 400); // Matches CSS transition time
    }, 3000);
}