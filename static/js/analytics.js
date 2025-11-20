/*
 * =========================================
 * CORELYTICS - ANALYTICS SCRIPT
 * =========================================
 * This file handles drawing all charts on the
 * analytics page using Google Charts.
 *
 * It assumes the following global variables are defined
 * in the <script> block of analytics.html:
 * - calorieConsumptionData
 * - mealTypeDistributionData
 * - weightProgressData
 */

// Load the Google Charts packages
google.charts.load('current', { 'packages': ['corechart', 'bar'] });

// Set the callback to run when the API is loaded
google.charts.setOnLoadCallback(drawCharts);

/**
 * Main function to draw all charts on the page.
 */
function drawCharts() {
    drawCalorieConsumptionChart();
    drawMealTypeDistributionChart();
    drawWeightProgressChart();
}

/**
 * Draws the "Daily Calorie Consumption" line chart.
 */
function drawCalorieConsumptionChart() {
    const chartDiv = document.getElementById('calorieConsumptionChart');
    if (!chartDiv || typeof calorieConsumptionData === 'undefined' || calorieConsumptionData.length <= 1) {
        chartDiv.innerHTML = '<p class="text-gray-500 text-center py-5">No calorie data to display yet.</p>';
        return;
    }

    // *** FIX: Convert date strings to JavaScript Date objects ***
    // Google Charts needs Date objects for a time-series axis, not strings.
    for (let i = 1; i < calorieConsumptionData.length; i++) {
        // [i][0] is the date string, e.g., "2025-11-10"
        const dateParts = calorieConsumptionData[i][0].split('-');
        if (dateParts.length === 3) {
            const year = parseInt(dateParts[0]);
            const month = parseInt(dateParts[1]) - 1; // JS months are 0-indexed
            const day = parseInt(dateParts[2]);
            
            // Overwrite the string with a new Date object
            calorieConsumptionData[i][0] = new Date(year, month, day);
        }
    }
    // *** END FIX ***

    const data = google.visualization.arrayToDataTable(calorieConsumptionData);

    const options = {
        title: 'Daily Calorie Consumption (Last 30 Days)',
        titleTextStyle: { color: '#374151', fontSize: 16, bold: true },
        curveType: 'function',
        legend: { position: 'none' },
        colors: ['#4CAF50'], // Green
        hAxis: { 
            title: 'Date', 
            textStyle: { color: '#6B7280' }, 
            format: 'MMM d' // This format now works because the data is a Date object
        },
        vAxis: { title: 'Calories', textStyle: { color: '#6B7280' }, minValue: 0 },
        chartArea: { width: '85%', height: '70%' },
        tooltip: { isHtml: true, trigger: 'hover' }
    };

    const chart = new google.visualization.LineChart(chartDiv);
    chart.draw(data, options);
}

/**
 * Draws the "Meal Type Distribution" pie chart.
 */
function drawMealTypeDistributionChart() {
    const chartDiv = document.getElementById('mealTypeDistributionChart');
    if (!chartDiv || typeof mealTypeDistributionData === 'undefined' || mealTypeDistributionData.length <= 1) {
        chartDiv.innerHTML = '<p class="text-gray-500 text-center py-5">No meal data to display yet.</p>';
        return;
    }

    const data = google.visualization.arrayToDataTable(mealTypeDistributionData);

    const options = {
        title: 'Distribution by Meal Type (Last 30 Days)', // Updated title
        titleTextStyle: { color: '#374151', fontSize: 16, bold: true },
        pieHole: 0.4,
        colors: ['#FACC15', '#FB923C', '#EF4444', '#3B82F6', '#6366F1', '#8B5CF6'],
        legend: { position: 'right', textStyle: { color: '#4B5563' } },
        chartArea: { width: '90%', height: '80%' },
        tooltip: { text: 'value', trigger: 'hover' },
        pieSliceText: 'percentage'
    };

    const chart = new google.visualization.PieChart(chartDiv);
    chart.draw(data, options);
}

/**
 * Draws the "Weight Progress" column chart.
 */
function drawWeightProgressChart() {
    const chartDiv = document.getElementById('weightProgressChart');
    if (!chartDiv || typeof weightProgressData === 'undefined' || weightProgressData.length <= 1) {
        chartDiv.innerHTML = '<p class="text-gray-500 text-center py-5">No weight data set in profile.</p>';
        return;
    }

    const data = google.visualization.arrayToDataTable(weightProgressData);

    const options = {
        title: 'Weight Progress',
        titleTextStyle: { color: '#374151', fontSize: 16, bold: true },
        legend: { position: 'none' },
        colors: ['#0EA5E9', '#F97316'], // Blue for current, Orange for target
        hAxis: { textStyle: { color: '#6B7280' } },
        vAxis: { title: 'Weight (kg)', textStyle: { color: '#6B7280' }, minValue: 0 },
        chartArea: { width: '70%', height: '70%' },
        tooltip: { isHtml: true, trigger: 'hover' },
        bars: 'vertical'
    };

    const chart = new google.visualization.ColumnChart(chartDiv);
    chart.draw(data, options);
}

// Redraw charts on window resize for responsiveness
window.addEventListener('resize', drawCharts);