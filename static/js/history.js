/*
 * =========================================
 * CORELYTICS - HISTORY SCRIPT
 * =========================================
 * This file handles the modal popup for viewing
 * daily meal details on the history page.
 */

document.addEventListener('DOMContentLoaded', function() {
    
    const mealDetailModal = document.getElementById('mealDetailModal');
    
    if (mealDetailModal) {
        // Listen for the 'show.bs.modal' event, triggered by Bootstrap
        mealDetailModal.addEventListener('show.bs.modal', function (event) {
            
            // Button that triggered the modal
            const button = event.relatedTarget; 
            
            // Extract info from data-* attributes
            const date = button.getAttribute('data-date');
            const mealsJson = button.getAttribute('data-meals');
            
            let meals = [];
            try {
                // Parse the JSON string of meals
                meals = JSON.parse(mealsJson.trim());
            } catch (e) {
                console.error("Error parsing meal data:", e, mealsJson);
                meals = []; // Default to empty array on error
            }

            // Update the modal's content
            const modalTitle = mealDetailModal.querySelector('#modalDate');
            const mealListContainer = mealDetailModal.querySelector('#mealList');

            modalTitle.textContent = date;
            mealListContainer.innerHTML = ''; // Clear previous content

            if (meals.length > 0) {
                meals.forEach(meal => {
                    const mealItem = document.createElement('div');
                    // Use flex classes for responsive layout
                    mealItem.className = 'd-flex flex-column flex-md-row justify-content-between align-items-start md:items-center bg-gray-50 p-3 rounded-lg shadow-sm';
                    
                    const calories = parseFloat(meal.estimated_calories || 0).toFixed(0);
                    
                    mealItem.innerHTML = `
                        <div class="font-medium text-gray-900 mb-1 md:mb-0 w-full md:w-1/2">
                            ${meal.meal_description} 
                            <span class="text-sm text-gray-600 block md:inline"> (${meal.meal_type}, ${meal.portion_size})</span>
                        </div>
                        <div class="text-indigo-600 font-semibold md:text-center w-full md:w-1/4">${calories} kcal</div>
                        <div class="text-gray-500 text-sm md:text-center w-full md:w-1/4">${meal.formatted_log_time}</div>
                    `;
                    mealListContainer.appendChild(mealItem);
                });
            } else {
                mealListContainer.innerHTML = '<p class="text-gray-600 text-center">No meals logged for this day.</p>';
            }
        });
    }
});