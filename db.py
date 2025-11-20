import os
import mysql.connector
import logging
from flask import g

def get_db_connection():
    """
    Establishes and returns a database connection.
    Uses Flask's 'g' object to store the connection for the duration of the request.
    """
    # 1. Check if connection already exists for this specific request
    if 'db' not in g:
        try:
            # 2. Create the connection if it doesn't exist
            conn = mysql.connector.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                user=os.getenv('DB_USER', 'root'),
                # Use empty string '' for XAMPP default, not None
                password=os.getenv('DB_PASSWORD', ''),
                database=os.getenv('DB_NAME', 'corelytics')
            )
            
            # 3. Store it in 'g' so we can reuse it later in the same request
            g.db = conn
            
        except mysql.connector.Error as err:
            logging.error(f"Error connecting to database: {err}")
            raise

    # 4. Return the existing (or newly created) connection
    return g.db

def close_db(e=None):
    """Closes the database connection if it exists."""
    db = g.pop('db', None)

    if db is not None:
        db.close()