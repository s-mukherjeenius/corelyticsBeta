/*
 * =========================================
 * CORELYTICS - MEAL PLANNER SCRIPT
 * =========================================
 * This file handles the AJAX request to generate
 * a new meal plan from the Gemini API and 
 * allows downloading it as a PDF.
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // --- DOM Elements ---
    const generatePlanBtn = document.getElementById('generatePlanBtn');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    
    const loadingSpinner = document.getElementById('loadingSpinner'); // The large spinner
    const mealPlanDisplay = document.getElementById('mealPlanDisplay');
    const mealPlanText = document.getElementById('mealPlanText');
    const errorMessage = document.getElementById('errorMessage');
    
    // NEW: Download Button
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');

    // --- Generate Plan Logic ---
    if (generatePlanBtn) {
        generatePlanBtn.addEventListener('click', async function() {
            
            // 1. Set UI to loading state
            generatePlanBtn.disabled = true;
            if (btnText) btnText.textContent = 'Generating...';
            if (btnSpinner) btnSpinner.style.display = 'inline-block';

            if (loadingSpinner) loadingSpinner.style.display = 'block'; 
            if (mealPlanDisplay) mealPlanDisplay.style.display = 'none';
            if (errorMessage) errorMessage.style.display = 'none';
            if (mealPlanText) mealPlanText.innerHTML = ''; 

            try {
                // 2. Make the API call
                const response = await fetch('/api/generate-meal-plan', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const result = await response.json();

                // 3. Handle the response
                if (result.success) {
                    if (mealPlanText) {
                        if (typeof marked !== 'undefined') {
                            mealPlanText.innerHTML = marked.parse(result.meal_plan);
                        } else {
                            console.error('Marked.js library not loaded.');
                            mealPlanText.textContent = result.meal_plan;
                        }
                    }
                    if (mealPlanDisplay) {
                        mealPlanDisplay.style.display = 'block';
                        // Smooth scroll to the result
                        mealPlanDisplay.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                } else {
                    if (errorMessage) {
                        errorMessage.textContent = result.message || 'An unknown error occurred.';
                        errorMessage.style.display = 'block';
                    }
                }

            } catch (error) {
                console.error('Error generating meal plan:', error);
                if (errorMessage) {
                    errorMessage.textContent = 'A network error occurred. Please try again.';
                    errorMessage.style.display = 'block';
                }
            } finally {
                // Reset UI
                generatePlanBtn.disabled = false;
                if (btnText) btnText.textContent = 'Generate My Meal Plan';
                if (btnSpinner) btnSpinner.style.display = 'none';
                if (loadingSpinner) loadingSpinner.style.display = 'none';
            }
        });
    }

    // --- NEW: Download PDF Logic ---
    if (downloadPdfBtn) {
        downloadPdfBtn.addEventListener('click', function() {
            const element = document.getElementById('mealPlanText');
            
            // Options for the PDF generation
            const opt = {
                margin:       [0.5, 0.5], // top/bottom, left/right
                filename:     'Corelytics_Meal_Plan.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2 }, // Higher scale for better quality
                jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' },
                pagebreak:    { mode: ['avoid-all', 'css', 'legacy'] } // Try to avoid breaking tables/paragraphs
            };

            // Use html2pdf library to generate and save
            // Note: We clone the element to avoid modifying the visible one if we needed to tweaks styles for print
            html2pdf().set(opt).from(element).save();
        });
    }
});