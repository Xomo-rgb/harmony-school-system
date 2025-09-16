from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_db_connection
from utils import log_activity
from werkzeug.security import check_password_hash, generate_password_hash
# --- CHANGES START HERE ---
import psycopg2
import psycopg2.extras
# --- CHANGES END HERE ---

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    user_role = session['role']
    conn = get_db_connection()
    # Use the correct cursor factory
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            new_full_name = request.form.get('full_name')
            new_email = request.form.get('email')

            if not new_full_name or not new_email:
                flash("Full name and email cannot be empty.", "error")
                cursor.close()
                return redirect(url_for('profile.settings'))

            cursor.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (new_email, user_id))
            if cursor.fetchone():
                flash("This email address is already in use by another account.", "error")
                cursor.close()
                return redirect(url_for('profile.settings'))
            
            cursor.execute("UPDATE users SET full_name = %s, email = %s WHERE user_id = %s", (new_full_name, new_email, user_id))
            conn.commit()

            session['full_name'] = new_full_name
            session['email'] = new_email

            log_activity("User updated their profile (name/email).")
            flash("Your profile has been updated successfully.", "success")

        elif action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not all([current_password, new_password, confirm_password]):
                flash("Please fill out all password fields.", "error")
                cursor.close()
                return redirect(url_for('profile.settings'))

            if new_password != confirm_password:
                flash("New password and confirmation do not match.", "error")
                cursor.close()
                return redirect(url_for('profile.settings'))

            cursor.execute("SELECT password FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()

            if not user or not check_password_hash(user['password'], current_password):
                flash("Your current password is incorrect.", "error")
                cursor.close()
                return redirect(url_for('profile.settings'))
            
            new_hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (new_hashed_password, user_id))
            conn.commit()

            log_activity("User changed their own password successfully.")
            flash("Your password has been updated successfully.", "success")
        
        cursor.close()
        return redirect(url_for('profile.settings'))

    # This part handles the GET request (when the page first loads)
    cursor.execute("SELECT full_name, email FROM users WHERE user_id = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    
    if user_role == 'teacher':
        return render_template('teacher_settings.html', user_data=user_data)
    elif user_role == 'accounts':
        return render_template('accounts_settings.html', user_data=user_data)
    elif user_role == 'school_admin':
        return render_template('school_admin_settings.html', user_data=user_data)
    else: # Default for System Admin
        return render_template('settings.html', user_data=user_data)