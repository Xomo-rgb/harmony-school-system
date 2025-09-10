from functools import wraps
from flask import session, flash, redirect, url_for
from db import get_db_connection

# This decorator is unchanged
def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for('admin.unauthorized'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# --- UPGRADED LOGGING FUNCTION ---
def log_activity(action_description, user_id=None, user_full_name=None):
    """
    Records an activity. Can be called with specific user info (for logins)
    or will get it from the session automatically (for most actions).
    """
    try:
        # If user info is not provided, get it from the session
        if user_id is None and 'user_id' in session:
            user_id = session['user_id']
        
        if user_full_name is None and 'full_name' in session:
            user_full_name = session['full_name']
            
        # If we still don't have a name (e.g., failed login), use a placeholder
        if user_full_name is None:
            user_full_name = "System/Unknown"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_logs (user_id, user_full_name, action) VALUES (%s, %s, %s)",
            (user_id, user_full_name, action_description)
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")