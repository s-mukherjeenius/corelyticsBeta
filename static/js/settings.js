/*
 * =========================================
 * CORELYTICS - SETTINGS SCRIPT
 * =========================================
 * This file handles all interactivity on the
 * settings page, including profile picture previews,
 * form submission, modals, and API calls.
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // --- Global Elements ---
    // Note: showToast is globally available from main.js
    
    // --- Helper: Modal Toggling ---
    const allModals = document.querySelectorAll('.page-modal');
    
    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
            const form = modal.querySelector('form');
            if (form) form.reset();
        }
    }

    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    }

    // Add listeners to all close buttons
    document.querySelectorAll('.page-modal .page-modal-close, .page-modal [data-modal-id]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modalId = e.currentTarget.dataset.modalId || e.currentTarget.closest('.page-modal').id;
            if (modalId) {
                closeModal(modalId);
            }
        });
    });

    // --- Helper: Button Loading State ---
    function setButtonLoading(button, isLoading) {
        if (!button) return;
        const text = button.querySelector('.btn-text');
        const spinner = button.querySelector('.btn-spinner');

        if (isLoading) {
            button.disabled = true;
            if (text) text.style.display = 'none';
            if (spinner) spinner.style.display = 'inline-block';
        } else {
            button.disabled = false;
            if (text) text.style.display = 'inline-block';
            if (spinner) spinner.style.display = 'none';
        }
    }

    // --- 1. NEW: Image Preview Logic ---
    // Handles immediate preview when a user selects a file
    const profilePicInput = document.getElementById('profilePicInput');
    const profilePicPreview = document.getElementById('profilePicPreview');

    if (profilePicInput && profilePicPreview) {
        profilePicInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // Basic validation: 2MB limit
                if (file.size > 2 * 1024 * 1024) { 
                    window.showToast('File is too large. Max size is 2MB.', 'error');
                    this.value = ''; // Clear input
                    return;
                }
                // Use FileReader to show preview
                const reader = new FileReader();
                reader.onload = function(e) {
                    profilePicPreview.src = e.target.result;
                }
                reader.readAsDataURL(file);
            }
        });
    }


    // --- 2. Settings Form (Profile & Goals) ---
    const settingsForm = document.getElementById('settingsForm');
    const saveProfileBtn = document.getElementById('saveProfileBtn');
    const saveGoalsBtn = document.getElementById('saveGoalsBtn');

    if (settingsForm) {
        settingsForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            
            setButtonLoading(saveProfileBtn, true);
            setButtonLoading(saveGoalsBtn, true);

            // UPDATED: Use FormData to support file uploads
            // This automatically grabs all inputs, including the file input
            const formData = new FormData(settingsForm);

            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    // IMPORTANT: Do NOT set Content-Type header here.
                    // The browser automatically sets 'multipart/form-data' with the correct boundary.
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    window.showToast(result.message, 'success');
                } else {
                    window.showToast(result.message, 'error');
                }
            } catch (error) {
                console.error('Error updating settings:', error);
                window.showToast('An unexpected network error occurred.', 'error');
            } finally {
                setButtonLoading(saveProfileBtn, false);
                setButtonLoading(saveGoalsBtn, false);
            }
        });
    }

    // --- 3. Change Password Modal ---
    const changePasswordBtn = document.getElementById('changePasswordBtn');
    const changePasswordForm = document.getElementById('changePasswordForm');
    const submitChangePasswordBtn = document.getElementById('submitChangePasswordBtn');

    if (changePasswordBtn) {
        changePasswordBtn.addEventListener('click', () => {
            openModal('changePasswordModal');
        });
    }

    if (changePasswordForm && submitChangePasswordBtn) {
        changePasswordForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            setButtonLoading(submitChangePasswordBtn, true);

            const currentPassword = document.getElementById('currentPassword').value;
            const newPassword = document.getElementById('newPassword').value;
            const confirmNewPassword = document.getElementById('confirmNewPassword').value;

            if (newPassword !== confirmNewPassword) {
                window.showToast('New password and confirmation do not match.', 'error');
                setButtonLoading(submitChangePasswordBtn, false);
                return;
            }

            try {
                const response = await fetch('/api/update-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword
                    })
                });
                const result = await response.json();

                if (result.success) {
                    window.showToast(result.message, 'success');
                    closeModal('changePasswordModal');
                } else {
                    window.showToast(result.message, 'error');
                }
            } catch (error) {
                console.error('Error changing password:', error);
                window.showToast('An error occurred. Please try again.', 'error');
            } finally {
                setButtonLoading(submitChangePasswordBtn, false);
            }
        });
    }

    // --- 4. Toggle 2FA ---
    const toggle2FABtn = document.getElementById('toggle2FABtn');
    if (toggle2FABtn) {
        toggle2FABtn.addEventListener('click', async () => {
            setButtonLoading(toggle2FABtn, true);

            try {
                const response = await fetch('/api/toggle-2fa', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const result = await response.json();

                if (result.success) {
                    window.showToast(result.message, 'success');
                    const btnText = toggle2FABtn.querySelector('.btn-text');
                    if (result.two_factor_enabled) {
                        btnText.innerHTML = '<i class="fas fa-mobile-alt me-2"></i>Disable 2FA';
                    } else {
                        btnText.innerHTML = '<i class="fas fa-mobile-alt me-2"></i>Enable 2FA';
                    }
                } else {
                    window.showToast(result.message, 'error');
                }
            } catch (error) {
                console.error('Error toggling 2FA:', error);
                window.showToast('An error occurred. Please try again.', 'error');
            } finally {
                setButtonLoading(toggle2FABtn, false);
            }
        });
    }
            
    // --- 5. Export Data ---
    const exportDataBtn = document.getElementById('exportDataBtn');
    if (exportDataBtn) {
        exportDataBtn.addEventListener('click', async () => {
            setButtonLoading(exportDataBtn, true);
            try {
                const response = await fetch('/api/export-data');
                if (response.ok) {
                    const blob = await response.blob();
                    const contentDisposition = response.headers.get('content-disposition');
                    let filename = 'corelytics_data.json';
                    if (contentDisposition) {
                        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                        if (filenameMatch && filenameMatch.length > 1) {
                            filename = filenameMatch[1];
                        }
                    }
                    
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = downloadUrl;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(downloadUrl);
                    a.remove();
                    
                    window.showToast('Data export started!', 'success');
                } else {
                    const result = await response.json();
                    window.showToast('Failed to export data: ' + result.message, 'error');
                }
            } catch (error) {
                console.error('Error exporting data:', error);
                window.showToast('An error occurred during data export.', 'error');
            } finally {
                setButtonLoading(exportDataBtn, false);
            }
        });
    }

    // --- 6. Delete Account ---
    const deleteAccountBtn = document.getElementById('deleteAccountBtn');
    const confirmDeleteAccountBtn = document.getElementById('confirmDeleteAccountBtn');
    const deletePasswordConfirm = document.getElementById('deletePasswordConfirm');

    if (deleteAccountBtn) {
        deleteAccountBtn.addEventListener('click', () => {
            openModal('deleteAccountConfirmModal');
        });
    }

    if (confirmDeleteAccountBtn) {
        confirmDeleteAccountBtn.addEventListener('click', async () => {
            setButtonLoading(confirmDeleteAccountBtn, true);

            const passwordToConfirm = deletePasswordConfirm.value;

            try {
                const response = await fetch('/api/delete-account', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: passwordToConfirm })
                });

                const result = await response.json();

                if (result.success) {
                    window.showToast(result.message, 'success');
                    closeModal('deleteAccountConfirmModal');
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 1500);
                } else {
                    window.showToast(result.message, 'error');
                    setButtonLoading(confirmDeleteAccountBtn, false);
                }
            } catch (error) {
                console.error('Error deleting account:', error);
                window.showToast('An error occurred. Please try again.', 'error');
                setButtonLoading(confirmDeleteAccountBtn, false);
            }
        });
    }
});