/*
 * =========================================
 * CORELYTICS - DASHBOARD SCRIPT
 * =========================================
 * This file handles interactivity for the main
 * dashboard, including the "Add Meal" modal
 * and the Google Pie Chart.
 */

// --- 1. Google Charts Logic ---

// Load the visualization libraries
google.charts.load("current", { packages: ["corechart"] });
// Set the callback to run when the Google Visualization API is loaded.
google.charts.setOnLoadCallback(drawChart);

/**
 * Draws the daily calorie pie chart.
 * Reads data from the #piechart_3d element's data attributes.
 */
function drawChart() {
    const chartDiv = document.getElementById('piechart_3d');
    if (!chartDiv) {
        console.error("Chart div 'piechart_3d' not found.");
        return;
    }

    // Read initial data from the HTML data attributes
    let dailyBudget = parseFloat(chartDiv.dataset.budget);
    let consumedCalories = parseFloat(chartDiv.dataset.consumed);

    // Ensure values are valid numbers
    dailyBudget = isNaN(dailyBudget) ? 0 : dailyBudget;
    consumedCalories = isNaN(consumedCalories) ? 0 : consumedCalories;

    let dataArray;
    let chartColors;
    let chartTitle = 'Daily Calorie Overview';

    if (dailyBudget <= 0) {
        // Fallback: No budget set, just show consumed
        dataArray = [
            ['Category', 'Calories'],
            ['Consumed', consumedCalories],
            ['Budget Not Set', 1] // Add 1 to show a slice
        ];
        chartColors = ['#4CAF50', '#D1D5DB']; // Green, Grey
    } else if (consumedCalories > dailyBudget) {
        // Surplus scenario
        let surplus = consumedCalories - dailyBudget;
        dataArray = [
            ['Category', 'Calories'],
            ['Budget Consumed', dailyBudget],
            ['Surplus', surplus]
        ];
        chartColors = ['#4CAF50', '#ef4444']; // Green, Red
        chartTitle = `Over Budget by ${surplus.toFixed(0)} Cal`;
    } else {
        // Remaining budget scenario
        let remaining = dailyBudget - consumedCalories;
        dataArray = [
            ['Category', 'Calories'],
            ['Consumed', consumedCalories],
            ['Remaining', remaining]
        ];
        chartColors = ['#4CAF50', '#3B82F6']; // Green, Blue
        chartTitle = `Remaining: ${remaining.toFixed(0)} Cal`;
    }

    const data = google.visualization.arrayToDataTable(dataArray);

    const options = {
        title: chartTitle,
        titleTextStyle: {
            color: '#374151',
            fontSize: 16,
            bold: true
        },
        is3D: false,
        pieHole: 0.6,
        backgroundColor: 'transparent',
        colors: chartColors,
        pieSliceText: 'none',
        tooltip: { isHtml: true, trigger: 'hover' },
        chartArea: {
            left: '5%',
            top: '15%',
            width: '90%',
            height: '70%'
        },
        legend: {
            position: 'right',
            alignment: 'center',
            textStyle: { color: '#374151', fontSize: 14 }
        },
        animation: {
            duration: 500,
            easing: 'out',
            startup: true
        }
    };

    const chart = new google.visualization.PieChart(chartDiv);
    chart.draw(data, options);
}

/**
 * Redraws the chart with new consumed values.
 * @param {number} newConsumed - The new total calories consumed.
 */
function redrawChart(newConsumed) {
    const chartDiv = document.getElementById('piechart_3d');
    if (!chartDiv) return;

    chartDiv.dataset.consumed = newConsumed; // Update the data attribute
    drawChart(); // Call the main draw function
}


// --- 2. Dashboard Interactivity ---

document.addEventListener('DOMContentLoaded', function() {
    
    // --- Modal Elements ---
    const addIntakeBtn = document.getElementById('addIntakeBtn');
    // *** FIX: Find the modal by its ID ***
    const addMealModal = document.getElementById('addMealModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const mealTypeSelect = document.getElementById('mealTypeSelect');
    const mealDescriptionInput = document.getElementById('mealDescriptionInput');
    const portionSizeSelect = document.getElementById('portionSizeSelect');
    const submitMealBtn = document.getElementById('submitMealBtn');
    const submitMealText = document.getElementById('submitMealText');
    const submitMealSpinner = document.getElementById('submitMealSpinner');

    // --- UI Elements to Update ---
    const dailyCalorieBucket = document.getElementById('dailyCalorieBucket');
    const mealLogsList = document.getElementById('mealLogsList');
    const totalConsumedToday = document.getElementById('totalConsumedToday');
    const noMealsMessage = document.getElementById('noMealsMessage');
    const mealLogsContainer = document.getElementById('mealLogsContainer');
    const toggleMealLogsBtn = document.getElementById('toggleMealLogsBtn');

    /**
     * Resets the "Add Meal" modal to its default state.
     */
    function resetModal() {
        if (!addMealModal) return;
        mealTypeSelect.value = 'Breakfast';
        portionSizeSelect.value = 'Medium';
        mealDescriptionInput.value = '';
        
        submitMealBtn.disabled = false;
        submitMealText.style.display = 'inline';
        submitMealSpinner.style.display = 'none';
    }

    /**
     * Opens the "Add Meal" modal.
     */
    function openModal() {
        if (addMealModal) {
            resetModal();
            // *** FIX: Use the 'show' class for our custom modal ***
            addMealModal.classList.add('show');
        }
    }

    /**
     * Closes the "Add Meal" modal.
     */
    function closeModal() {
        if (addMealModal) {
            // *** FIX: Use the 'show' class for our custom modal ***
            addMealModal.classList.remove('show');
        }
    }

    /**
     * Handles the submission of the new meal.
     */
    async function handleSubmitMeal() {
        const mealType = mealTypeSelect.value;
        const portionSize = portionSizeSelect.value;
        const mealDescription = mealDescriptionInput.value.trim();

        if (!mealDescription) {
            // Use the global showToast function from main.js
            window.showToast('Please describe your meal!', 'error');
            return;
        }

        // Show loading state
        submitMealBtn.disabled = true;
        submitMealText.style.display = 'none';
        submitMealSpinner.style.display = 'inline-block';

        try {
            const response = await fetch('/api/log-meal', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    meal_type: mealType,
                    meal_description: mealDescription,
                    portion_size: portionSize
                })
            });

            const result = await response.json();

            if (result.success) {
                window.showToast('Meal logged successfully!', 'success');
                closeModal();

                // Update the UI dynamically
                updateDashboardUI(
                    result.total_calories_consumed,
                    result.meal_type,
                    result.meal_description,
                    result.estimated_calories,
                    result.formatted_log_time
                );
                
                // Redraw the pie chart
                redrawChart(result.total_calories_consumed);

            } else {
                window.showToast('Error logging meal: ' + result.message, 'error');
            }
        } catch (error) {
            console.error('Error submitting meal:', error);
            window.showToast('An error occurred. Please try again.', 'error');
        } finally {
            // Reset button state
            submitMealBtn.disabled = false;
            submitMealText.style.display = 'inline';
            submitMealSpinner.style.display = 'none';
        }
    }

    /**
     * Updates the dashboard UI with the new meal log.
     */
    function updateDashboardUI(newTotal, mealType, mealDescription, estimatedCalories, logTime) {
        // Update total in metric card
        if (dailyCalorieBucket) {
            dailyCalorieBucket.innerHTML = `${newTotal.toFixed(1)}<span class="unit">Cal</span>`;
        }
        
        // Update total in meal list
        if (totalConsumedToday) {
            totalConsumedToday.textContent = `${newTotal.toFixed(1)} Cal`;
        }

        // Remove the "No meals" message if it exists
        if (noMealsMessage && noMealsMessage.parentNode) {
            noMealsMessage.remove();
        }

        // Create and prepend the new log item
        const newLogItem = document.createElement('li');
        newLogItem.className = 'list-group-item d-flex justify-content-between align-items-center';
        newLogItem.innerHTML = `
            <span>
                <b>${mealType}:</b> ${mealDescription}
                <span class="text-muted text-sm">(${logTime})</span>
            </span>
            <span class="badge">${estimatedCalories.toFixed(0)} Cal</span>
        `;

        if (mealLogsList) {
            const totalItemLi = totalConsumedToday.closest('li');
            if (totalItemLi) {
                // Insert the new log *before* the "Total" li
                mealLogsList.insertBefore(newLogItem, totalItemLi);
            } else {
                // Fallback: just append
                mealLogsList.appendChild(newLogItem);
            }
        }
    }

    // --- Event Listeners ---

    // Modal listeners
    if (addIntakeBtn) {
        addIntakeBtn.addEventListener('click', openModal);
    }
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }
    if (submitMealBtn) {
        submitMealBtn.addEventListener('click', handleSubmitMeal);
    }
    // Add Enter key listener to modal input
    if (mealDescriptionInput) {
        mealDescriptionInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSubmitMeal();
            }
        });
    }

    // "View All" logs toggle
    if (mealLogsContainer && toggleMealLogsBtn) {
        toggleMealLogsBtn.addEventListener('click', function() {
            const isExpanded = mealLogsContainer.classList.toggle('expanded');
            toggleMealLogsBtn.classList.toggle('expanded', isExpanded);

            if (isExpanded) {
                toggleMealLogsBtn.innerHTML = 'View Less <i class="fas fa-chevron-up ml-2"></i>';
            } else {
                toggleMealLogsBtn.innerHTML = 'View All <i class="fas fa-chevron-down ml-2"></i>';
            }
        });
    }

});