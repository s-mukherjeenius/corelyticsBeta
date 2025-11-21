import os
import requests
import json
import logging
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session, 
    get_flashed_messages, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

# Import the shared database connection function
from db import get_db_connection

# Fetch the Google Client ID once from the environment
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
if not GOOGLE_CLIENT_ID:
    logging.warning("GOOGLE_CLIENT_ID environment variable is not set. Google Sign-In will not work.")

# Create a Blueprint
bp = Blueprint('auth', __name__, template_folder='../templates')

# --- Authentication Routes (Login, Signup, Logout) ---

@bp.route('/')
def index():
    """Renders the combined auth page showing LOGIN by default."""
    if "user_email" in session:
        # NEW: Redirect Admins to the Admin Dashboard
        if session.get("role") == 'admin':
            return redirect(url_for('admin.admin_dashboard'))

        if session.get("onboarding_complete", False):
            return redirect(url_for('main.dashboard'))
        else:
            return redirect(url_for('main.onboarding'))
    
    return render_template('auth.html', google_client_id=GOOGLE_CLIENT_ID, mode='login')

@bp.route('/signup')
def signup():
    """Renders the combined auth page showing SIGNUP by default."""
    if "user_email" in session:
        # NEW: Redirect Admins
        if session.get("role") == 'admin':
            return redirect(url_for('admin.admin_dashboard'))
        return redirect(url_for('main.dashboard'))
    
    return render_template('auth.html', google_client_id=GOOGLE_CLIENT_ID, mode='signup')

@bp.route('/signup', methods=['POST'])
def handle_signup():
    """Handles manual user signup (email/password)."""
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if not all([full_name, email, password, confirm_password]):
        flash("Please fill in all fields.", 'danger')
        return redirect(url_for('auth.signup'))
        
    if password != confirm_password:
        flash("Passwords do not match.", 'danger')
        return redirect(url_for('auth.signup'))

    hashed_password = generate_password_hash(password)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = %s", (email,))
        if cursor.fetchone()[0] > 0:
            flash("This email is already registered. Please log in.", 'danger')
            return redirect(url_for('auth.signup'))

        # NEW: Explicitly set role to 'user'
        cursor.execute(
            "INSERT INTO users (full_name, email, password, signup_method, onboarding_complete, role) VALUES (%s, %s, %s, %s, %s, 'user')",
            (full_name, email, hashed_password, 'manual', False)
        )
        conn.commit()

        new_user_id = cursor.lastrowid

        # Set session variables
        session["user_email"] = email
        session["full_name"] = full_name
        session["profile_picture"] = None
        session["onboarding_complete"] = False
        session["user_id"] = new_user_id
        session["role"] = "user" # NEW: Store role in session
        
        logging.info(f"New user signed up: {email} (ID: {new_user_id}, Role: user)")

        flash('Account created successfully! Please complete your profile.', 'success')
        return redirect(url_for('main.onboarding'))

    except mysql.connector.Error as e:
        logging.error(f"Database error during signup: {e}")
        flash("An error occurred during registration. Please try again.", 'danger')
        if conn: conn.rollback()
        return redirect(url_for('auth.signup'))
    except Exception as e:
        logging.error(f"Unexpected error during signup: {e}")
        flash("An unexpected error occurred. Please try again.", 'danger')
        return redirect(url_for('auth.signup'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/login', methods=['POST'])
def handle_login():
    """Handles user login (email/password)."""
    email = request.form.get('email')
    password = request.form.get('password')

    if not all([email, password]):
        flash("Please enter both email and password.", 'danger')
        return redirect(url_for('auth.index'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # NEW: Select 'role' from DB
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and user.get('password') and check_password_hash(user['password'], password):
            session["user_email"] = user['email']
            session["full_name"] = user['full_name']
            session["profile_picture"] = user['profile_picture_url']
            session["onboarding_complete"] = bool(user['onboarding_complete'])
            session["user_id"] = user['id'] 
            
            # NEW: Handle Role
            role = user.get('role', 'user')
            session["role"] = role

            logging.info(f"User {email} logged in. Role: {role}")
            
            # NEW: Admin Redirection Logic
            if role == 'admin':
                flash('Welcome back, Administrator.', 'success')
                return redirect(url_for('admin.admin_dashboard'))

            # Standard User Redirection
            if session.get("onboarding_complete", False):
                flash('Logged in successfully!', 'success')
                return redirect(url_for('main.dashboard'))
            else:
                flash('Welcome! Please complete your profile.', 'info')
                return redirect(url_for('main.onboarding'))
        else:
            flash("Invalid email or password.", 'danger')
            logging.warning(f"Failed login attempt for email: {email}")
            return redirect(url_for('auth.index'))

    except mysql.connector.Error as e:
        logging.error(f"Database error during login: {e}")
        flash("An error occurred during login. Please try again.", 'danger')
        return redirect(url_for('auth.index'))
    except Exception as e:
        logging.error(f"Unexpected error during login: {e}")
        flash("An unexpected error occurred. Please try again.", 'danger')
        return redirect(url_for('auth.index'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/google-signup', methods=['POST'])
def google_signup():
    """Handles Google One Tap sign-up/login via ID token verification."""
    data = request.get_json()
    id_token = data.get('id_token')

    if not GOOGLE_CLIENT_ID:
        logging.error("Error: GOOGLE_CLIENT_ID environment variable not set.")
        return jsonify({"success": False, "message": "Server configuration error."}), 500

    conn = None
    cursor = None
    try:
        # Verify the token with Google
        response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}")
        response.raise_for_status() 
        payload = response.json()

        if payload.get("aud") != GOOGLE_CLIENT_ID:
            logging.error(f"Invalid client ID: Expected {GOOGLE_CLIENT_ID}, Got {payload.get('aud')}")
            return jsonify({"success": False, "message": "Invalid Google client ID."}), 400

        email = payload.get("email")
        if not email:
            logging.error("Email not found in Google token payload.")
            return jsonify({"success": False, "message": "Email not found in Google token."}), 400

        full_name = payload.get("name", "Google User")
        google_picture_url = payload.get("picture", None)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # NEW: Fetch role as well
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        onboarding_status = False
        user_id = None
        final_profile_pic_url = google_picture_url 
        user_role = 'user' # Default for new users

        if not user:
            # New user: Insert into database with role 'user'
            cursor.execute(
                "INSERT INTO users (full_name, email, signup_method, onboarding_complete, profile_picture_url, role) VALUES (%s, %s, %s, %s, %s, 'user')",
                (full_name, email, 'google', False, google_picture_url)
            )
            conn.commit()
            user_id = cursor.lastrowid 
            logging.info(f"New Google user signed up: {email}, ID: {user_id}")
        else:
            user_id = user['id']
            onboarding_status = bool(user.get('onboarding_complete', False))
            current_db_pic = user.get('profile_picture_url')
            user_role = user.get('role', 'user') # Fetch existing role
            
            is_custom_picture = current_db_pic and "static/uploads" in current_db_pic

            if is_custom_picture:
                final_profile_pic_url = current_db_pic
            else:
                cursor.execute(
                    "UPDATE users SET profile_picture_url = %s WHERE email = %s",
                    (google_picture_url, email)
                )
                conn.commit()
                final_profile_pic_url = google_picture_url

        # Set all session variables
        session["user_email"] = email
        session["full_name"] = full_name
        session["profile_picture"] = final_profile_pic_url
        session["onboarding_complete"] = onboarding_status
        session["user_id"] = user_id 
        session["role"] = user_role # NEW: Store role in session
        
        logging.info(f"Session set for Google user: {email}. Role: {user_role}")

        return jsonify({
            "success": True, 
            "message": "Login successful!", 
            "redirect_to_onboarding": not onboarding_status
        })

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during Google token verification: {e}")
        return jsonify({"success": False, "message": "Failed to verify Google token."}), 500
    except mysql.connector.Error as e:
        logging.error(f"Database error during Google signup: {e}")
        if conn: conn.rollback()
        return jsonify({"success": False, "message": "Database error during login."}), 500
    except Exception as e:
        logging.error(f"Google sign-in error: {e}")
        return jsonify({"success": False, "message": "Google sign-in failed."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@bp.route('/logout')
def logout():
    """Logs out the user by clearing the session."""
    logging.info(f"User {session.get('user_email')} logging out. SESSION CLEARED.")
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.index'))