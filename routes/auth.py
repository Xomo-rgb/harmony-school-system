from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_db_connection
from werkzeug.security import check_password_hash
from utils import log_activity # <-- Import the logger

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        session.clear()

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return redirect(url_for('auth.login'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id, full_name, email, password, role FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            # --- LOG SUCCESSFUL LOGIN ---
            # We pass the user info directly because they aren't in the session yet
            log_activity(f"User logged in successfully.", user_id=user['user_id'], user_full_name=user['full_name'])

            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['email'] = user['email']
            session['role'] = user['role']

            user_role = user['role']
            if user_role == 'system_admin':
                return redirect(url_for('admin.system_admin_dashboard'))
            elif user_role == 'school_admin':
                return redirect(url_for('admin.school_admin_dashboard'))
            elif user_role == 'teacher':
                return redirect(url_for('teacher.teacher_dashboard'))
            elif user_role == 'accounts':
                return redirect(url_for('admin.accounts_dashboard'))
            else:
                flash("Your user role is undefined. Please contact an administrator.", "error")
                return redirect(url_for('auth.login'))
        else:
            # --- LOG FAILED LOGIN ATTEMPT ---
            log_activity(f"Failed login attempt for email: '{email}'.")
            
            flash("Invalid email or password. Please try again.", "error")
            return redirect(url_for('auth.login'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    # --- LOG LOGOUT ---
    # We log this before clearing the session so we know who logged out
    if 'full_name' in session:
        log_activity(f"User '{session['full_name']}' logged out.")

    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for('auth.login'))