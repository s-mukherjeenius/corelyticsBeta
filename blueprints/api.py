import logging
import os # NEW: For file path operations
from flask import (
    Blueprint, request, redirect, url_for, flash, session, jsonify, current_app, send_file
)
import mysql.connector
from datetime import datetime, date
import json
from werkzeug.utils import secure_filename # NEW: For secure file saving
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO

# Import shared functions, classes, and blueprints
from db import get_db_connection
from utils import calculate_age, calculate_bmr, get_daily_calorie_budget, CustomJSONEncoder
import gemini_client 
from blueprints.main import login_required 

# Create the Blueprint
bp = Blueprint('api', __name__, url_prefix='/api')

# --- API Routes ---

@bp.route('/save-onboarding-data', methods=['POST'])
@login_required
def save_onboarding_data():
    """Saves user's onboarding profile data."""
    user_email = session.get("user_email")
    user_id = session.get("user_id")
    
    if not user_id:
        logging.error(f"Session missing user_id for email: {user_email}. Session is invalid.")
        return jsonify({"success": False, "message": "Session expired or invalid. Please log in again."}), 401

    data = request.json
    logging.info(f"Saving onboarding data for {user_email}. Data keys: {data.keys()}")

    required_fields = ['dob', 'currentWeight', 'height', 'targetWeight', 'targetDate', 'gender', 'activityLevel']
    if not all(field in data and data[field] for field in required_fields):
        missing = [field for field in required_fields if field not in data or not data[field]]
        logging.warning(f"Missing required field(s) during onboarding: {missing}")
        return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

    conn = None
    cursor = None
    try:
        dob = datetime.strptime(data['dob'], '%Y-%m-%d').date()
        target_date = datetime.strptime(data['targetDate'], '%Y-%m-%d').date()
        current_weight = float(data['currentWeight'])
        height = float(data['height'])
        target_weight = float(data['targetWeight'])
        gender = data['gender']
        activity_level = data['activityLevel']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET dob = %s, current_weight = %s, height = %s, target_weight = %s, 
                target_date = %s, gender = %s, activity_level = %s, onboarding_complete = TRUE
            WHERE id = %s
            """,
            (dob, current_weight, height, target_weight, target_date, gender, activity_level, user_id)
        )
        conn.commit()

        session["onboarding_complete"] = True
        flash("Your profile has been successfully updated!", 'success')
        logging.info(f"Onboarding data saved successfully for {user_email}.")
        return jsonify({"success": True, "message": "Onboarding data saved successfully!"})

    except ValueError:
        logging.error(f"Invalid date or numerical format for {user_email} during onboarding save.")
        return jsonify({"success": False, "message": "Invalid date or numerical format provided."}), 400
    except mysql.connector.Error as e:
        logging.error(f"Database error saving onboarding data for {user_email}: {e}")
        if conn: conn.rollback()
        return jsonify({"success": False, "message": "Failed to save data due to a database error."}), 500
    except Exception as e:
        logging.error(f"Error saving onboarding data for {user_email}: {e}")
        return jsonify({"success": False, "message": "Failed to save data due to an internal error."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/log-meal', methods=['POST'])
@login_required
def log_meal():
    """Logs a meal for the authenticated user, estimating calories."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Session expired. Please log in again."}), 401

    data = request.get_json()
    logging.info(f"Meal logging attempt for user {user_id}. Data: {data}")

    meal_type = data.get('meal_type')
    meal_description = data.get('meal_description')
    portion_size = data.get('portion_size')

    if not all([meal_type, meal_description, portion_size]):
        return jsonify({"success": False, "message": "Missing meal details."}), 400

    conn = None
    cursor = None
    try:
        estimated_calories = gemini_client.estimate_calories_with_gemini(
            meal_description, meal_type, portion_size
        )
        
        if estimated_calories == 0.0:
            flash("Could not estimate calories (AI returned 0). Logged as 0 calories.", 'warning')
            logging.warning("Gemini calorie estimation returned 0.0.")

        current_date = date.today()
        current_time = datetime.now().time()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            INSERT INTO meal_logs (user_id, meal_type, meal_description, portion_size, estimated_calories, log_date, log_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, meal_type, meal_description, portion_size, estimated_calories, current_date, current_time)
        )
        conn.commit()

        cursor.execute(
            "SELECT SUM(estimated_calories) AS total FROM meal_logs WHERE user_id = %s AND log_date = %s",
            (user_id, current_date)
        )
        total_today_result = cursor.fetchone()
        total_today = float(total_today_result['total']) if total_today_result and total_today_result['total'] is not None else 0.0

        logging.info(f"Meal logged with {estimated_calories} calories. Total for day: {total_today}.")

        return jsonify({
            "success": True,
            "message": "Meal logged successfully!",
            "estimated_calories": estimated_calories,
            "total_calories_consumed": total_today,
            "meal_type": meal_type,
            "meal_description": meal_description,
            "portion_size": portion_size,
            "formatted_log_time": current_time.strftime('%H:%M')
        })

    except mysql.connector.Error as e:
        if conn: conn.rollback()
        logging.error(f"ERROR: Database error saving meal log for {user_id}: {e}")
        return jsonify({"success": False, "message": "Failed to save meal data."}), 500
    except Exception as e:
        logging.error(f"ERROR: Unexpected error during meal logging for {user_id}: {e}")
        if conn: conn.rollback()
        return jsonify({"success": False, "message": "An unexpected error occurred."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/generate-meal-plan', methods=['POST'])
@login_required
def generate_meal_plan():
    """Generates a meal plan using Gemini based on user profile data."""
    user_id = session.get("user_id")
    if not user_id:
         return jsonify({"success": False, "message": "Session expired. Please log in again."}), 401

    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT full_name, dob, current_weight, height, target_weight, gender, activity_level FROM users WHERE id = %s",
            (user_id,)
        )
        user_data = cursor.fetchone()

        if not user_data:
            return jsonify({"success": False, "message": "User data not found."}), 404
        
        dob = user_data.get('dob')
        current_weight = float(user_data['current_weight']) if user_data.get('current_weight') is not None else None
        height = float(user_data['height']) if user_data.get('height') is not None else None
        gender = user_data.get('gender')
        target_weight = float(user_data['target_weight']) if user_data.get('target_weight') is not None else None

        if not all([dob, current_weight, height, gender]):
            return jsonify({"success": False, "message": "Incomplete profile data."}), 400

        age_years = calculate_age(dob)
        gender_male = (gender.lower() == 'male')
        
        bmr_raw = calculate_bmr(current_weight, height, age_years, gender_male=gender_male) 
        daily_calorie_budget = get_daily_calorie_budget(
            bmr_raw,
            user_data.get('activity_level'),
            current_weight,
            target_weight
        )

        user_profile_for_gemini = {
            'full_name': user_data['full_name'],
            'age_years': age_years,
            'current_weight': current_weight,
            'height': height,
            'gender': gender,
            'activity_level': user_data.get('activity_level'),
            'target_weight': target_weight,
            'daily_calorie_budget': daily_calorie_budget
        }

        meal_plan = gemini_client.generate_meal_plan_with_gemini(user_profile_for_gemini)
        
        if "Error" in meal_plan or "Failed" in meal_plan or "Could not" in meal_plan:
            logging.error(f"Failed to generate meal plan for {user_id}: {meal_plan}")
            return jsonify({"success": False, "message": meal_plan}), 500
        
        logging.info(f"Meal plan generated successfully for {user_id}.")
        return jsonify({"success": True, "meal_plan": meal_plan})

    except mysql.connector.Error as e:
        logging.error(f"Database error for meal plan generation for {user_id}: {e}")
        return jsonify({"success": False, "message": "Failed to fetch user data."}), 500
    except Exception as e:
        logging.error(f"Unexpected error during meal plan generation for {user_id}: {e}")
        return jsonify({"success": False, "message": "An unexpected error occurred."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- NEW CHAT ROUTES ---

@bp.route('/start-new-chat', methods=['POST'])
@login_required
def start_new_chat():
    """Creates a new conversation entry in the DB."""
    user_id = session.get("user_id")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create a placeholder conversation
        cursor.execute(
            "INSERT INTO conversations (user_id, title) VALUES (%s, 'New Chat')",
            (user_id,)
        )
        conn.commit()
        new_id = cursor.lastrowid
        
        # Update session
        session['current_conversation_id'] = new_id
        session['chat_history'] = [] # Clear context for Gemini
        session.modified = True
        
        return jsonify({"success": True, "conversation_id": new_id})
    except Exception as e:
        logging.error(f"Error starting chat: {e}")
        return jsonify({"success": False, "message": "Failed to start new chat"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/get-conversation/<int:conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    """Loads a specific conversation history."""
    user_id = session.get("user_id")
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Security check: ensure this conversation belongs to this user
        cursor.execute("SELECT id FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Fetch messages
        cursor.execute(
            "SELECT role, message FROM chat_logs WHERE conversation_id = %s ORDER BY id ASC",
            (conv_id,)
        )
        logs = cursor.fetchall()
        
        # Rebuild session history so Gemini remembers context if they continue this chat
        formatted_history = [{"role": log['role'], "parts": [{"text": log['message']}]} for log in logs]
        session['chat_history'] = formatted_history
        session['current_conversation_id'] = conv_id
        session.modified = True

        return jsonify({"success": True, "history": logs})
    except Exception as e:
        logging.error(f"Error fetching conversation: {e}")
        return jsonify({"success": False, "message": "Failed to load conversation"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """
    Handles chat messages:
    1. Manages Conversation ID (Creates new if null).
    2. Saves USER message to DB.
    3. Sends to Gemini.
    4. Saves BOT response to DB.
    """
    user_email = session.get("user_email")
    user_id = session.get("user_id")
    conversation_id = session.get('current_conversation_id')
    
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"success": False, "message": "Message cannot be empty."}), 400

    # Ensure session history exists
    if 'chat_history' not in session:
        session['chat_history'] = []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Auto-Start Conversation if none selected
        if not conversation_id:
            cursor.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s)", (user_id, "New Chat"))
            conn.commit()
            conversation_id = cursor.lastrowid
            session['current_conversation_id'] = conversation_id
        
        # 2. Update Title if it's the first message (still 'New Chat')
        # We use a simplified title generator: first 30 chars of message
        new_title = (user_message[:30] + '...') if len(user_message) > 30 else user_message
        cursor.execute(
            "UPDATE conversations SET title = %s WHERE id = %s AND title = 'New Chat'",
            (new_title, conversation_id)
        )
        conn.commit()

        # 3. Save USER message to DB
        cursor.execute(
            "INSERT INTO chat_logs (user_id, conversation_id, role, message) VALUES (%s, %s, 'user', %s)",
            (user_id, conversation_id, user_message)
        )
        conn.commit()

        # Update Session Context
        session['chat_history'].append({"role": "user", "parts": [{"text": user_message}]})
        session.modified = True

        # 4. Prepare Gemini Context
        contents_for_gemini = [
            {"role": "user", "parts": [{"text": gemini_client.LOGIC_PERSONALITY_PROMPT}]},
            {"role": "model", "parts": [{"text": "Understood. I am LOGIC. How can I help?"}]},
        ]
        contents_for_gemini.extend(session['chat_history'])

        # 5. Call Gemini API
        bot_response = gemini_client.generate_chat_response(contents_for_gemini)

        if bot_response:
            # 6. Save BOT response to DB
            cursor.execute(
                "INSERT INTO chat_logs (user_id, conversation_id, role, message) VALUES (%s, %s, 'model', %s)",
                (user_id, conversation_id, bot_response)
            )
            conn.commit()

            # Update Session Context
            session['chat_history'].append({"role": "model", "parts": [{"text": bot_response}]})
            session.modified = True
            
            return jsonify({"success": True, "response": bot_response})
        else:
            # Rollback user message from session history (not DB, to keep record of attempt)
            session['chat_history'].pop()
            session.modified = True
            return jsonify({"success": False, "message": "Our AI service is currently busy. Please try again."}), 503

    except mysql.connector.Error as e:
        logging.error(f"Database error during chat for {user_email}: {e}")
        return jsonify({"success": False, "message": "Database error occurred."}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during chat for {user_email}: {e}.")
        return jsonify({"success": False, "message": "An unexpected error occurred."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- UPDATED SETTINGS ROUTE ---
@bp.route('/settings', methods=['POST'])
@login_required
def settings_post():
    """Handles updating user settings including profile picture."""
    user_email = session.get("user_email")
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "message": "Session expired. Please log in again."}), 401

    # Handle Text Data (request.form)
    try:
        full_name = request.form.get("full_name")
        dob_str = request.form.get("dob")
        current_weight = float(request.form.get("current_weight", 0))
        height = float(request.form.get("height", 0))
        target_weight = float(request.form.get("target_weight", 0))
        target_date_str = request.form.get("target_date")
        gender = request.form.get("gender")
        activity_level = request.form.get("activity_level")

        # Parse dates
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

        if not all([full_name, dob, current_weight, height, target_weight, gender, activity_level, target_date]):
            return jsonify({"success": False, "message": "All fields are required."}), 400
            
    except (ValueError, TypeError) as e:
        logging.error(f"Invalid data format settings update for {user_email}: {e}")
        return jsonify({"success": False, "message": "Invalid number or date format."}), 400

    # Handle File Upload (request.files)
    file = request.files.get('profile_pic')
    filename_to_save = None

    if file and file.filename != '':
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
            import time
            # Generate secure filename: user_ID_timestamp.ext
            ext = file.filename.rsplit('.', 1)[1].lower()
            new_filename = f"user_{user_id}_{int(time.time())}.{ext}"
            
            # Ensure upload directory exists: static/uploads
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            # Save file
            file.save(os.path.join(upload_folder, new_filename))
            
            # Generate URL path for DB
            filename_to_save = url_for('static', filename=f'uploads/{new_filename}')
        else:
            return jsonify({"success": False, "message": "Invalid file type. Use JPG or PNG."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Construct Query based on whether image was uploaded
        if filename_to_save:
            query = """
                UPDATE users
                SET full_name=%s, dob=%s, current_weight=%s, height=%s,
                    target_weight=%s, gender=%s, activity_level=%s, target_date=%s, profile_picture_url=%s
                WHERE id=%s
            """
            params = (full_name, dob, current_weight, height, target_weight, gender, activity_level, target_date, filename_to_save, user_id)
            
            # Update session immediately
            session["profile_picture"] = filename_to_save
        else:
            query = """
                UPDATE users
                SET full_name=%s, dob=%s, current_weight=%s, height=%s,
                    target_weight=%s, gender=%s, activity_level=%s, target_date=%s
                WHERE id=%s
            """
            params = (full_name, dob, current_weight, height, target_weight, gender, activity_level, target_date, user_id)

        cursor.execute(query, params)
        conn.commit()

        session["full_name"] = full_name
        logging.info(f"Settings updated successfully for {user_email}.")
        return jsonify({"success": True, "message": "Settings updated successfully!"})

    except mysql.connector.Error as e:
        logging.error(f"Database error updating settings for {user_email}: {e}")
        if conn: conn.rollback()
        return jsonify({"success": False, "message": "Failed to save settings."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/update-password', methods=['POST'])
@login_required
def update_password():
    """Handles changing the user's password."""
    user_email = session.get("user_email")
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "message": "Session expired. Please log in again."}), 401

    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"success": False, "message": "All password fields are required."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT password, signup_method FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "User not found."}), 404
        
        if user['signup_method'] != 'manual':
            return jsonify({"success": False, "message": "Password cannot be changed for Google accounts."}), 400

        if not user.get('password') or not check_password_hash(user['password'], current_password):
            return jsonify({"success": False, "message": "Incorrect current password."}), 403

        hashed_password = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
        conn.commit()

        logging.info(f"Password updated successfully for {user_email}.")
        return jsonify({"success": True, "message": "Password changed successfully!"})

    except mysql.connector.Error as e:
        logging.error(f"Database error during password update for {user_email}: {e}")
        return jsonify({"success": False, "message": "Database error during password update."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
@bp.route('/toggle-2fa', methods=['POST'])
@login_required
def toggle_2fa():
    """Toggles two-factor authentication for the user."""
    user_email = session.get("user_email")
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "message": "Session expired. Please log in again."}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT two_factor_enabled FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if user is None:
            return jsonify({"success": False, "message": "User not found."}), 404

        current_status = bool(user.get('two_factor_enabled', False))
        new_status = not current_status

        cursor.execute("UPDATE users SET two_factor_enabled = %s WHERE id = %s", (new_status, user_id))
        conn.commit()

        message = f"Two-Factor Authentication {'enabled' if new_status else 'disabled'}."
        logging.info(f"2FA status changed to {new_status} for {user_email}.")
        return jsonify({"success": True, "message": message, "two_factor_enabled": new_status})

    except mysql.connector.Error as e:
        logging.error(f"Database error toggling 2FA for {user_email}: {e}")
        return jsonify({"success": False, "message": "Database error occurred."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Permanently deletes a user's account and all their data."""
    user_email = session.get("user_email")
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "message": "Session expired. Please log in again."}), 401

    password = request.json.get('password')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT password, signup_method FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "User not found."}), 404

        if user['signup_method'] == 'manual':
            if not password:
                return jsonify({"success": False, "message": "Password is required."}), 400
            if not user.get('password') or not check_password_hash(user['password'], password):
                return jsonify({"success": False, "message": "Incorrect password."}), 403
        
        cursor.execute("DELETE FROM meal_logs WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()

        session.clear()
        logging.warning(f"ACCOUNT DELETED for {user_email} (ID: {user_id}).")
        return jsonify({"success": True, "message": "Your account has been successfully deleted."})

    except mysql.connector.Error as e:
        if conn: conn.rollback()
        logging.error(f"Database error during account deletion for {user_email}: {e}")
        return jsonify({"success": False, "message": "Database error during account deletion."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/export-data', methods=['GET'])
@login_required
def export_data():
    """Exports user's data as a JSON file."""
    user_email = session.get("user_email")
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "message": "Session expired. Please log in again."}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()

        if not user_data:
            return jsonify({"success": False, "message": "User data not found."}), 404
        
        user_data.pop('password', None)

        cursor.execute("SELECT * FROM meal_logs WHERE user_id = %s ORDER BY log_date ASC, log_time ASC", (user_id,))
        meal_logs = cursor.fetchall()

        export_content = {
            "user_profile": user_data,
            "meal_logs": meal_logs
        }

        output = BytesIO()
        output.write(json.dumps(export_content, indent=4, cls=CustomJSONEncoder).encode('utf-8'))
        output.seek(0)

        logging.info(f"Data exported successfully for {user_email}.")
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'corelytics_data_{user_id}.json'
        )

    except mysql.connector.Error as e:
        logging.error(f"Database error during data export for {user_email}: {e}")
        return jsonify({"success": False, "message": "Failed to export data."}), 500
    except Exception as e:
        logging.error(f"Unexpected error during data export for {user_email}: {e}")
        return jsonify({"success": False, "message": "An unexpected error occurred."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()