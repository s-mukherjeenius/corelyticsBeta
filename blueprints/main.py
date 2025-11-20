import logging
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session, 
    get_flashed_messages, jsonify, Response
)
import mysql.connector
from datetime import datetime, date, timedelta
from functools import wraps
import json

# Import shared functions and classes
from db import get_db_connection
from utils import calculate_age, calculate_bmr, get_daily_calorie_budget, CustomJSONEncoder

# Create the Blueprint
bp = Blueprint('main', __name__, template_folder='../templates')


# --- Decorator for Authentication ---

def login_required(f):
    """
    Decorator to ensure a user is logged in and onboarded.
    Redirects to login or onboarding page as needed.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('auth.index'))
        
        if not session.get("onboarding_complete", False):
            # Allow access to the onboarding page ITSELF
            # AND allow access to the API endpoint that saves the onboarding data
            allowed_endpoints = ['main.onboarding', 'api.save_onboarding_data']
            
            if request.endpoint not in allowed_endpoints:
                flash('Please complete your profile to access the dashboard.', 'warning')
                return redirect(url_for('main.onboarding'))
        
        return f(*args, **kwargs)
    return decorated_function

# --- Main Application Routes ---

@bp.route('/dashboard')
@login_required
def dashboard():
    """Renders the user dashboard with personalized data."""
    user_email = session["user_email"]
    user_id = session["user_id"] # Get user_id from session
    logging.info(f"Dashboard access for user: {user_email} (ID: {user_id})")

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT full_name, profile_picture_url, dob, current_weight, height, target_weight, target_date, gender, activity_level FROM users WHERE id = %s",
            (user_id,)
        )
        user_data = cursor.fetchone()

        if not user_data:
            flash('Your user data could not be found. Please log out and log in again.', 'danger')
            logging.error(f"User data NOT found in DB for session user {user_email}. Logging out.")
            return redirect(url_for('auth.logout'))

        # --- NEW: Sync session profile picture with Database ---
        # This ensures the header image updates correctly when navigating back to the dashboard
        session['profile_picture'] = user_data.get('profile_picture_url')
        session.modified = True
        # -------------------------------------------------------

        # Calculate BMR, Budget, and Days Left
        bmr = None
        daily_calorie_budget = None
        days_left_to_target = None
        age_years = 0

        dob = user_data.get('dob')
        current_weight = float(user_data['current_weight']) if user_data.get('current_weight') is not None else None
        height = float(user_data['height']) if user_data.get('height') is not None else None
        gender = user_data.get('gender')
        
        if dob and current_weight is not None and height is not None and gender is not None:
            age_years = calculate_age(dob)
            gender_male = (gender.lower() == 'male')
            
            bmr_raw = calculate_bmr(current_weight, height, age_years, gender_male=gender_male)
            bmr = round(bmr_raw) # Store the raw BMR
            
            daily_calorie_budget = get_daily_calorie_budget(
                bmr_raw, 
                user_data.get('activity_level'), 
                current_weight, 
                float(user_data.get('target_weight')) if user_data.get('target_weight') else None
            )

        target_date = user_data.get('target_date')
        if target_date:
            today = date.today()
            if target_date > today:
                days_left_to_target = (target_date - today).days
            else:
                days_left_to_target = 0

        # Fetch today's meal logs
        today_date = date.today()
        cursor.execute(
            "SELECT meal_type, meal_description, portion_size, estimated_calories, DATE_FORMAT(log_time, '%H:%i') AS formatted_log_time FROM meal_logs WHERE user_id = %s AND log_date = %s ORDER BY log_time DESC",
            (user_id, today_date)
        )
        daily_intake_logs = cursor.fetchall()
        
        total_calories_consumed = sum(log['estimated_calories'] for log in daily_intake_logs if log['estimated_calories'] is not None)

        return render_template(
            'dashboard.html',
            full_name=user_data.get("full_name", "User"),
            profile_picture=user_data.get("profile_picture_url", None),
            current_weight=current_weight,
            target_weight=float(user_data.get('target_weight')) if user_data.get('target_weight') else None,
            bmr=bmr,
            daily_calorie_budget=daily_calorie_budget,
            total_calories_consumed=total_calories_consumed,
            daily_intake_logs=daily_intake_logs,
            days_left_to_target=days_left_to_target
        )

    except mysql.connector.Error as e:
        logging.error(f"Database error in dashboard for {user_email}: {e}")
        flash("Could not load dashboard data due to a database error.", 'danger')
        return redirect(url_for('auth.index')) # Redirect to login on critical error
    except Exception as e:
        logging.error(f"Unexpected error in dashboard for {user_email}: {e}")
        flash("An unexpected error occurred while loading dashboard.", 'danger')
        return redirect(url_for('auth.index'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/onboarding')
@login_required # This will check for login, but allow access even if onboarding_complete is False
def onboarding():
    """Renders the onboarding questions page for new users."""
    if session.get("onboarding_complete", False):
        flash('Your profile is already complete!', 'info')
        return redirect(url_for('main.dashboard'))

    return render_template('onboarding_questions.html', full_name=session.get('full_name', 'there'))

@bp.route('/history')
@login_required
def history():
    """Renders the meal log history page."""
    user_email = session["user_email"]
    user_id = session["user_id"]
    logging.info(f"History access for user: {user_email} (ID: {user_id})")

    conn = None
    cursor = None
    meal_logs_by_date = {}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch all meal logs for the user, ordered
        cursor.execute(
            """
            SELECT
                log_date,
                DATE_FORMAT(log_date, '%Y-%m-%d') AS formatted_log_date,
                meal_type,
                meal_description,
                portion_size,
                estimated_calories,
                DATE_FORMAT(log_time, '%H:%i') AS formatted_log_time
            FROM meal_logs
            WHERE user_id = %s
            ORDER BY log_date DESC, log_time DESC
            """,
            (user_id,)
        )
        all_logs = cursor.fetchall()
        logging.info(f"Fetched {len(all_logs)} meal logs for user {user_id}.")

        # Organize logs by date
        for log in all_logs:
            date_str = log['formatted_log_date']
            if date_str not in meal_logs_by_date:
                meal_logs_by_date[date_str] = {
                    'total_calories': 0.0,
                    'meals': []
                }
            
            calories = float(log.get('estimated_calories', 0.0) or 0.0)
            log['estimated_calories'] = calories # Ensure it's a float
            
            meal_logs_by_date[date_str]['meals'].append(log)
            meal_logs_by_date[date_str]['total_calories'] += calories
        
        logging.info(f"Organized logs into {len(meal_logs_by_date)} unique dates.")

    except mysql.connector.Error as e:
        logging.error(f"Database error fetching history for {user_email}: {e}")
        flash("Could not load meal history due to a database error.", 'danger')
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logging.error(f"Unexpected error in history route for {user_email}: {e}")
        flash("An unexpected error occurred while loading history.", 'danger')
        return redirect(url_for('main.dashboard'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('history.html', meal_logs_by_date=meal_logs_by_date)

@bp.route('/meal-chart-planner')
@login_required
def meal_chart_planner():
    """Renders the meal chart planner page."""
    return render_template('meal_chart_planner.html')

@bp.route('/analytics')
@login_required
def analytics():
    """Renders the analytics page with dynamic data from the user's logs."""
    user_email = session['user_email']
    user_id = session['user_id']
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT current_weight, target_weight FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            flash('Your user data could not be found.', 'danger')
            return redirect(url_for('main.dashboard'))

        # --- 1. Daily Calorie Consumption Trend (Last 30 Days) ---
        thirty_days_ago = date.today() - timedelta(days=30)
        
        cursor.execute(
            """
            SELECT
                DATE_FORMAT(log_date, %s) AS consumption_date,
                IFNULL(SUM(estimated_calories), 0) AS total_calories
            FROM meal_logs
            WHERE user_id = %s AND log_date >= %s
            GROUP BY log_date
            ORDER BY log_date ASC
            """,
            ('%Y-%m-%d', user_id, thirty_days_ago) 
        )
        daily_calories_result = cursor.fetchall()
        
        calorie_consumption_data = [['Date', 'Calories']]
        calorie_consumption_data.extend([
            [item['consumption_date'], float(item['total_calories'])] for item in daily_calories_result
        ])

        # --- 2. Meal Type Distribution (Last 30 Days) ---
        cursor.execute(
            """
            SELECT 
                meal_type, 
                IFNULL(SUM(estimated_calories), 0) AS total_calories
            FROM meal_logs 
            WHERE user_id = %s 
            AND log_date >= %s
            GROUP BY meal_type
            """,
            (user_id, thirty_days_ago) 
        )
        meal_type_result = cursor.fetchall()
        
        meal_type_distribution_data = [['Meal Type', 'Calories']]
        meal_type_distribution_data.extend([
            [item['meal_type'].title(), float(item['total_calories'])] for item in meal_type_result
        ])
        if len(meal_type_distribution_data) <= 1:
            meal_type_distribution_data.append(['No Data', 0])

        # --- 3. Weight Progress Chart ---
        weight_progress_data = [['Label', 'Weight (kg)']]
        if user.get('current_weight'):
             weight_progress_data.append(['Current Weight', float(user['current_weight'])])
        if user.get('target_weight'):
             weight_progress_data.append(['Target Weight', float(user['target_weight'])])
        
        if len(weight_progress_data) <= 1:
            weight_progress_data.append(['No Data', 0])

        # --- 4. Insights & Summaries (All Time) ---
        cursor.execute(
            """
            SELECT 
                IFNULL(AVG(daily_total), 0) AS average_calories
            FROM (
                SELECT IFNULL(SUM(estimated_calories), 0) AS daily_total
                FROM meal_logs
                WHERE user_id = %s
                GROUP BY log_date
            ) AS daily_sums
            """,
            (user_id,)
        )
        avg_calories_result = cursor.fetchone()
        average_calories = round(float(avg_calories_result['average_calories'])) if avg_calories_result and avg_calories_result['average_calories'] else 0

        cursor.execute(
            """
            SELECT 
                IFNULL(SUM(estimated_calories), 0) AS total_monthly 
            FROM meal_logs 
            WHERE user_id = %s 
            AND MONTH(log_date) = MONTH(CURDATE()) 
            AND YEAR(log_date) = YEAR(CURDATE())
            """,
            (user_id,)
        )
        monthly_calories_result = cursor.fetchone()
        total_monthly_calories = int(monthly_calories_result['total_monthly']) if monthly_calories_result and monthly_calories_result['total_monthly'] else 0
        
        longest_streak_days = 0 # Placeholder

        logging.info(f"Successfully processed analytics data for user {user_id}")

        return render_template(
            'analytics.html',
            calorie_consumption_data=json.dumps(calorie_consumption_data, cls=CustomJSONEncoder),
            meal_type_distribution_data=json.dumps(meal_type_distribution_data, cls=CustomJSONEncoder),
            weight_progress_data=json.dumps(weight_progress_data, cls=CustomJSONEncoder),
            average_calories=average_calories,
            total_monthly_calories=total_monthly_calories,
            longest_streak_days=longest_streak_days
        )

    except mysql.connector.Error as e:
        logging.error(f"Database error in analytics route for {user_email}: {e}")
        flash("Could not load analytics data due to a database error.", 'danger')
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logging.error(f"Unexpected error in analytics route for {user_email}: {e}")
        flash("An unexpected error occurred while loading analytics.", 'danger')
        return redirect(url_for('main.dashboard'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/logic')
@login_required
def logic():
    """
    Renders the LOGIC Chatbot page.
    Fetches recent conversation history for the sidebar.
    Clears current chat session ID so the user starts in a 'Select Chat' or 'New Chat' state.
    """
    user_id = session["user_id"]
    conn = None
    cursor = None
    recent_conversations = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch last 5 conversations for the sidebar
        cursor.execute(
            """
            SELECT id, title, DATE_FORMAT(created_at, '%b %d') as date_str 
            FROM conversations 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 5
            """,
            (user_id,)
        )
        recent_conversations = cursor.fetchall()
        
        # 2. Clear current session variables so page loads in "neutral" state
        session.pop('current_conversation_id', None)
        session['chat_history'] = []
        session.modified = True

    except mysql.connector.Error as e:
        logging.error(f"Database error in logic route: {e}")
        # No flash here to avoid annoying popups, just show empty sidebar
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template(
        'logic.html',
        recent_conversations=recent_conversations,
        chat_history=[] # Start empty, user selects from sidebar or creates new
    )

@bp.route("/settings", methods=["GET"])
@login_required
def settings_get():
    """Handles displaying the user settings page."""
    user_email = session["user_email"]
    user_id = session["user_id"]
    logging.info(f"--- Entering settings GET route for {user_email} ---")
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT full_name, email, dob, current_weight, height, target_weight, gender, activity_level, profile_picture_url, two_factor_enabled, target_date, signup_method FROM users WHERE id = %s",
            (user_id,),
        )
        user_data = cursor.fetchone()

        if not user_data:
            flash("Your user data could not be found.", "danger")
            return redirect(url_for("main.dashboard"))

        # Format dates for HTML date input
        if user_data.get("dob"):
            user_data["dob_formatted"] = user_data["dob"].strftime("%Y-%m-%d")
        if user_data.get("target_date"):
            user_data["target_date_formatted"] = user_data["target_date"].strftime("%Y-%m-%d")

        user_data["two_factor_enabled"] = bool(user_data.get("two_factor_enabled", False))

        return render_template("settings.html", **user_data)

    except mysql.connector.Error as e:
        logging.error(f"Database error fetching settings for {user_email}: {e}")
        flash("Could not load settings data due to a database error.", "danger")
        return redirect(url_for("main.dashboard"))
    except Exception as e:
        logging.error(f"Unexpected error in settings GET route for {user_email}: {e}")
        flash("An unexpected error occurred while loading settings.", "danger")
        return redirect(url_for("main.dashboard"))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/help')
@login_required
def help_page():
    """Renders the Help and Support page."""
    # We don't need to fetch complex data here because the header info
    # (Profile Pic) is handled by session variables in base.html
    return render_template('help.html')