/*
 * =========================================
 * CORELYTICS - MAIN JAVASCRIPT
 * =========================================
 * This file contains common scripts used across the
 * authenticated app, primarily for sidebar/nav logic.
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // --- Mobile Sidebar Toggle Logic (Updated for Locking) ---
    const sidebarToggle = document.getElementById('sidebarToggleMobile');
    const mobileSidebar = document.getElementById('mobileSidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const body = document.body;

    // Function to Open Sidebar & Lock Body
    function openSidebar() {
        if (!mobileSidebar) return;
        mobileSidebar.classList.add('show');
        overlay.classList.add('show');
        body.classList.add('no-scroll'); // Locks the background
    }

    // Function to Close Sidebar & Unlock Body
    function closeSidebar() {
        if (!mobileSidebar) return;
        mobileSidebar.classList.remove('show');
        overlay.classList.remove('show');
        body.classList.remove('no-scroll'); // Unlocks the background
    }

    if (sidebarToggle && mobileSidebar && overlay) {
        // Toggle Button Click
        sidebarToggle.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent bubbling
            if (mobileSidebar.classList.contains('show')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });

        // Close when clicking the overlay
        overlay.addEventListener('click', function() {
            closeSidebar();
        });

        // UX Improvement: Close sidebar when a link inside is clicked
        const sidebarLinks = mobileSidebar.querySelectorAll('a');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', closeSidebar);
        });
    }

    // --- Common Toast Message Function ---
    // This function can be called by other scripts if needed
    window.showToast = function(message, type = 'info') {
        const toastMessageBox = document.getElementById('toastMessageBox');
        if (!toastMessageBox) {
            console.error('Toast message box not found');
            return;
        }

        toastMessageBox.textContent = message;
        toastMessageBox.classList.remove('success', 'error', 'info', 'show');
        
        // Add the correct type class
        if (type === 'success' || type === 'danger') {
             toastMessageBox.classList.add(type === 'success' ? 'success' : 'error');
        } else {
             toastMessageBox.classList.add('info');
        }
        
        // Show the toast
        toastMessageBox.classList.add('show');

        // Clear existing timeout if any
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
            }, 400); // 400ms matches the CSS transition
        }, 3000);
    };

    // --- Flash Message Handling ---
    // Check for server-rendered flash messages and display them using the toast UI
    const flashMessages = document.querySelectorAll('.flash-message');
    if (flashMessages.length > 0) {
        flashMessages.forEach((flash, index) => {
            const message = flash.textContent;
            let type = 'info';
            if (flash.classList.contains('flash-success')) {
                type = 'success';
            } else if (flash.classList.contains('flash-danger')) {
                type = 'error';
            }
            
            // Stagger multiple messages so they don't overlap
            setTimeout(() => {
                window.showToast(message, type);
            }, index * 500);
        });
    }

});