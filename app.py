import os
import logging
from flask import Flask, session
from dotenv import load_dotenv

# --- 1. Load Environment Variables ---
# Load .env file for local development (Render will ignore this if file is missing)
load_dotenv()

# --- 2. Import Blueprints and Initializers ---
# Import these *after* load_dotenv()
from blueprints import auth, main, api
# NEW: Import the Admin Blueprint
from blueprints import admin 
import gemini_client
# Import the database functions
from db import close_db, get_db_connection

# --- 3. Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 4. Create and Configure the Flask App ---
app = Flask(__name__)
# Use a secure random key for production, fallback for local dev
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_fallback_secret_key')

# --- 5. Initialize the Gemini Model ---
if not gemini_client.initialize_gemini_model():
    logging.warning("Gemini AI features may not function correctly as no model could be initialized.")

# --- 6. Register Blueprints ---
app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)
app.register_blueprint(api.bp)
app.register_blueprint(admin.bp) # NEW: Register Admin Blueprint

# --- 7. Register Teardown Context ---
# This ensures the DB connection is closed automatically after every request
app.teardown_appcontext(close_db)

# --- 8. Middleware: Track Online Users & Security Headers ---

@app.before_request
def update_last_active():
    """
    Updates the 'last_active' timestamp for the logged-in user.
    This allows the Admin Dashboard to count 'Online Users'.
    """
    if "user_id" in session:
        # We only update if the user is logged in
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Update last_active to NOW()
            cursor.execute("UPDATE users SET last_active = NOW() WHERE id = %s", (session["user_id"],))
            conn.commit()
        except Exception as e:
            # Don't crash the app if tracking fails, just log it
            logging.error(f"Failed to update last_active: {e}")

@app.after_request
def add_security_headers(response):
    """
    Tells the browser specifically NOT to cache HTML pages.
    This prevents the 'Back Button' from showing sensitive data after logout.
    """
    # Only apply this to HTML pages (Dashboard, Settings, etc.)
    # We let CSS/JS/Images be cached so the site stays fast.
    if "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# --- 9. Run the Application ---
if __name__ == '__main__':
    # Keep debug=True for local, but never for production
    # Port 3000 is fine for local, Render handles its own port automatically
    app.run(debug=True, port=3000)