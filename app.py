import os
import logging
from flask import Flask
from dotenv import load_dotenv

# --- 1. Load Environment Variables ---
# Load .env file for local development (Render will ignore this if file is missing)
load_dotenv()

# --- 2. Import Blueprints and Initializers ---
# Import these *after* load_dotenv()
from blueprints import auth, main, api
import gemini_client
# Import the close_db function to register it with the app
from db import close_db

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

# --- 7. Register Teardown Context ---
# This ensures the DB connection is closed automatically after every request
# regardless of whether the request succeeded or failed.
app.teardown_appcontext(close_db)

# --- 8. Run the Application ---
if __name__ == '__main__':
    # Keep debug=True for local, but never for production
    # Port 3000 is fine for local, Render handles its own port automatically
    app.run(debug=True, port=3000)