/*
 * =========================================
 * CORELYTICS - ONBOARDING SCRIPT
 * =========================================
 * This file handles the multi-step questionnaire
 * for new user onboarding.
 */

document.addEventListener('DOMContentLoaded', () => {
    
    // --- Configuration ---
    const questions = [
        { id: 'q1', inputId: 'dobInput', type: 'date', key: 'dob' },
        { id: 'q2', inputName: 'gender', type: 'radio', key: 'gender' },
        { id: 'q3', inputId: 'currentWeightInput', unitId: 'weightUnit', type: 'number', key: 'currentWeight' },
        { id: 'q4', inputId: 'heightInput', unitId: 'heightUnit', type: 'number', key: 'height' },
        { id: 'q5', inputId: 'targetWeightInput', unitId: 'targetWeightUnit', type: 'number', key: 'targetWeight' },
        { id: 'q6', inputId: 'activityLevelInput', type: 'select', key: 'activityLevel' },
        { id: 'q7', inputId: 'targetDateInput', type: 'date', key: 'targetDate' }
    ];
    const totalQuestions = questions.length;

    // --- State ---
    let currentQuestionIndex = 0;
    const onboardingData = {};

    // --- DOM Elements ---
    const progressBarFill = document.getElementById('progressBarFill');
    const messageBox = document.getElementById('messageBox');
    const messageText = document.getElementById('messageText');
    let  messageBoxBtn = document.getElementById('messageBoxBtn');
    const questionCardsWrapper = document.getElementById('questionCardsWrapper');
    const submitBtn = document.getElementById('submitOnboardingBtn');

    // --- Functions ---

    /**
     * Updates the progress bar fill based on the current question index.
     */
    function updateProgressBar() {
        // Progress is based on *completed* steps.
        const progress = (currentQuestionIndex / totalQuestions) * 100;
        progressBarFill.style.width = `${progress}%`;
    }

    /**
     * Shows the pop-up message box with a specific message.
     * @param {string} message - The text to display.
     * @param {function} [callback] - Optional function to run when "Got it!" is clicked.
     */
    function showMessageBox(message, callback = null) {
        messageText.textContent = message;
        messageBox.classList.add('show');
        
        // Remove old listener if any and add new one
        const newBtn = messageBoxBtn.cloneNode(true); // Clone to remove listeners
        messageBoxBtn.parentNode.replaceChild(newBtn, messageBoxBtn);
        
        newBtn.onclick = () => {
            hideMessageBox();
            if (callback) {
                callback();
            }
        };
        // Re-assign element reference
        messageBoxBtn = newBtn;
    }

    /**
     * Hides the pop-up message box.
     */
    function hideMessageBox() {
        messageBox.classList.remove('show');
    }

    /**
     * Validates the current question's input and collects the data.
     * @returns {boolean} - True if valid, false if not.
     */
    function validateAndCollectData() {
        const config = questions[currentQuestionIndex];
        let inputElement, value, unitValue;

        switch (config.type) {
            case 'date':
                inputElement = document.getElementById(config.inputId);
                value = inputElement.value.trim();
                if (!value) {
                    showMessageBox("Oops! Please select a date before moving on. 😊");
                    return false;
                }
                const date = new Date(value);
                if (isNaN(date.getTime())) {
                    showMessageBox("Please enter a valid date.");
                    return false;
                }
                // Specific date logic
                if (config.id === 'q1') { // DOB
                    if (date > new Date()) {
                        showMessageBox("Your date of birth cannot be in the future!");
                        return false;
                    }
                } else if (config.id === 'q7') { // Target Date
                    const today = new Date();
                    today.setHours(0, 0, 0, 0); // Compare dates only
                    if (date < today) {
                        showMessageBox("Your target date should be today or in the future!");
                        return false;
                    }
                }
                onboardingData[config.key] = value;
                break;

            case 'radio':
                const selectedRadio = document.querySelector(`input[name="${config.inputName}"]:checked`);
                if (!selectedRadio) {
                    showMessageBox("Please make a selection before moving on. 😊");
                    return false;
                }
                value = selectedRadio.value;
                onboardingData[config.key] = value;
                break;

            case 'number':
                inputElement = document.getElementById(config.inputId);
                value = parseFloat(inputElement.value.trim());
                if (isNaN(value) || value <= 0) {
                    showMessageBox("Please enter a valid positive number.");
                    return false;
                }
                onboardingData[config.key] = value;
                // Handle units
                if (config.unitId) {
                    const unitElement = document.getElementById(config.unitId);
                    if (unitElement) {
                        unitValue = unitElement.value;
                        onboardingData[config.unitId] = unitValue; // e.g., 'weightUnit': 'kg'
                    }
                }
                break;

            case 'select':
                inputElement = document.getElementById(config.inputId);
                value = inputElement.value;
                if (!value) {
                    showMessageBox("Please select your activity level. 😊");
                    return false;
                }
                onboardingData[config.key] = value;
                break;

            default:
                return false;
        }
        return true;
    }

    /**
     * Moves the questionnaire to the next step with animations.
     */
    function nextQuestion() {
        if (!validateAndCollectData()) {
            return; // Stop if validation fails
        }

        // --- Special logic for linked units ---
        // If we just finished Q3 (weight), update the unit label in Q5
        if (questions[currentQuestionIndex].id === 'q3') {
            const weightUnit = onboardingData.weightUnit || 'kg';
            document.getElementById('targetWeightUnit').textContent = weightUnit;
        }

        // --- Animate current card out ---
        const currentQuestionElement = document.getElementById(questions[currentQuestionIndex].id);
        currentQuestionElement.classList.remove('active');
        currentQuestionElement.classList.add('leaving');

        currentQuestionIndex++;
        updateProgressBar();

        if (currentQuestionIndex < totalQuestions) {
            // --- Animate next card in ---
            const nextQuestionElement = document.getElementById(questions[currentQuestionIndex].id);
            nextQuestionElement.classList.add('entering');
            setTimeout(() => {
                nextQuestionElement.classList.remove('entering');
                nextQuestionElement.classList.add('active');
            }, 500); // Match CSS animation duration
        } else {
            // This case should be handled by the submit button's specific listener
            // but we'll log it just in case.
            console.log("Reached end of questions, awaiting submit.");
        }
    }

    /**
     * Prepares and submits the final onboarding data to the backend.
     */
    async function submitOnboardingData() {
        if (!validateAndCollectData()) {
            return; // Final validation
        }
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';

        // --- Prepare Payload ---
        // Data keys are already mapped correctly (e.g., 'dob', 'currentWeight')
        const payload = { ...onboardingData };

        // Convert units to backend standard (kg, cm)
        if (payload.weightUnit === 'lbs') {
            payload.currentWeight *= 0.453592;
            payload.targetWeight *= 0.453592;
        }
        if (payload.heightUnit === 'inches') {
            payload.height *= 2.54;
        }

        // Remove unit keys as backend doesn't need them
        delete payload.weightUnit;
        delete payload.heightUnit;
        delete payload.targetWeightUnit; // This was just a span's ID

        try {
            const response = await fetch('/api/save-onboarding-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (result.success) {
                showMessageBox("Awesome! All set. Redirecting you to your dashboard...", () => {
                    window.location.href = '/dashboard';
                });
            } else {
                showMessageBox(`Oh no! Something went wrong: ${result.message}. Please review your answers and try again.`);
                submitBtn.disabled = false;
                submitBtn.innerHTML = "Let's Go!";
                // Maybe reset to a specific question? For now, just re-enable submit.
                currentQuestionIndex = totalQuestions - 1; // Stay on last question
            }
        } catch (error) {
            console.error("Error submitting onboarding data:", error);
            showMessageBox("A network error occurred. Please check your connection and try again.");
            submitBtn.disabled = false;
            submitBtn.innerHTML = "Let's Go!";
        }
    }

    // --- Event Listeners ---
    
    // Add click listeners to all "Next" buttons
    questionCardsWrapper.querySelectorAll('button[data-next]').forEach(button => {
        button.addEventListener('click', nextQuestion);
    });

    // Add specific listener for the final "Submit" button
    if (submitBtn) {
        submitBtn.addEventListener('click', submitOnboardingData);
    }
    
    // Listen for Enter key on text/number inputs
    questionCardsWrapper.querySelectorAll('input[type="date"], input[type="number"]').forEach(input => {
        input.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault(); // Prevent form submission
                // Find the button in the same card and click it
                const parentCard = event.target.closest('.question-card');
                const nextButton = parentCard.querySelector('button');
                if (nextButton) {
                    nextButton.click();
                }
            }
        });
    });

    // --- Initialization ---
    updateProgressBar();
    // Ensure only the first question is active on load
    document.getElementById(questions[0].id).classList.add('active');
});