import logging
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from functools import wraps
import mysql.connector
from datetime import datetime

# Import shared DB connection
from db import get_db_connection

# Create the Blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- Admin Security Decorator ---
def admin_required(f):
    """
    Decorator to ensure the user is logged in AND is an admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access the admin panel.", "danger")
            return redirect(url_for('auth.index'))
        
        if session.get("role") != "admin":
            flash("Unauthorized access.", "danger")
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """
    Renders the Super Admin Dashboard with high-level statistics.
    Calculates initial 'Online' status based on a 1-minute window.
    """
    conn = None
    cursor = None
    stats = {
        "total_users": 0,
        "online_users": 0,
        "active_today": 0,
        "users_list": []
    }

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Total Registered Users (Excluding Admins)
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role != 'admin'")
        stats["total_users"] = cursor.fetchone()['count']

        # 2. Active Today
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count FROM meal_logs 
            WHERE log_date = CURDATE()
        """)
        stats["active_today"] = cursor.fetchone()['count']

        # 3. Fetch All Users (EXCLUDING ADMINS)
        # Updated to hide Super Admin from the table
        cursor.execute("""
            SELECT id, full_name, email, role, signup_method, last_active, created_at 
            FROM users 
            WHERE role != 'admin'
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        
        # 4. Process "Online" Status
        online_count = 0
        now = datetime.now()
        
        for user in users:
            if user['last_active']:
                time_diff = now - user['last_active']
                # Window set to 60 seconds
                user['is_online'] = time_diff.total_seconds() < 60 
                if user['is_online']:
                    online_count += 1
            else:
                user['is_online'] = False
        
        stats["online_users"] = online_count
        stats["users_list"] = users

    except mysql.connector.Error as e:
        logging.error(f"Admin Dashboard DB Error: {e}")
        flash("Error loading dashboard stats.", "danger")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('admin_dashboard.html', stats=stats)

@bp.route('/user/<int:user_id>/chats')
@admin_required
def view_user_chats(user_id):
    """
    Displays all conversations and chat logs for a specific user.
    """
    conn = None
    cursor = None
    user = None
    conversations = []
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Get User Details
        cursor.execute("SELECT id, full_name, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for('admin.admin_dashboard'))

        # 2. Get All Conversations for this user
        cursor.execute("""
            SELECT id, title, created_at 
            FROM conversations 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        conversations = cursor.fetchall()
        
        # 3. Get All Chat Logs
        cursor.execute("""
            SELECT conversation_id, role, message, created_at 
            FROM chat_logs 
            WHERE user_id = %s 
            ORDER BY created_at ASC
        """, (user_id,))
        all_logs = cursor.fetchall()
        
        # Attach logs to their respective conversations
        for conv in conversations:
            conv['messages'] = [log for log in all_logs if log['conversation_id'] == conv['id']]

    except mysql.connector.Error as e:
        logging.error(f"Error fetching chats for user {user_id}: {e}")
        flash("Error loading chats.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('admin_user_chats.html', user=user, conversations=conversations)

@bp.route('/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Permanently deletes a user and their logs."""
    if user_id == session.get('user_id'):
        flash("You cannot delete your own admin account.", "warning")
        return redirect(url_for('admin.admin_dashboard'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM meal_logs WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM chat_logs WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()

        flash("User account deleted successfully.", "success")
        logging.warning(f"Admin deleted user ID: {user_id}")

    except mysql.connector.Error as e:
        if conn: conn.rollback()
        logging.error(f"Error deleting user {user_id}: {e}")
        flash("Failed to delete user.", "danger")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/user/edit/<int:user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    """Updates user details directly from Admin Panel."""
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    role = request.form.get('role')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users 
            SET full_name = %s, email = %s, role = %s 
            WHERE id = %s
        """, (full_name, email, role, user_id))
        conn.commit()
        flash(f"User {full_name} updated successfully.", "success")

    except mysql.connector.Error as e:
        if conn: conn.rollback()
        logging.error(f"Error updating user {user_id}: {e}")
        flash("Failed to update user details.", "danger")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/api/stats')
@admin_required
def api_stats():
    """
    Returns JSON statistics for AJAX polling (Real-time updates).
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Total Users (Excluding Admins)
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role != 'admin'")
        total_users = cursor.fetchone()['count']

        # 2. Active Today
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count FROM meal_logs 
            WHERE log_date = CURDATE()
        """)
        active_today = cursor.fetchone()['count']

        # 3. Get list of Online IDs (Active within last 1 MINUTE)
        cursor.execute("""
            SELECT id FROM users 
            WHERE last_active >= NOW() - INTERVAL 1 MINUTE
            AND role != 'admin'
        """)
        online_results = cursor.fetchall()
        online_ids = [row['id'] for row in online_results]

        return jsonify({
            "success": True,
            "online_users_count": len(online_ids),
            "online_user_ids": online_ids,
            "total_users": total_users,
            "active_today": active_today
        })

    except Exception as e:
        logging.error(f"API Stats Error: {e}")
        return jsonify({"success": False}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()