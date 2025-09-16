from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_db_connection
from utils import role_required, log_activity
from werkzeug.security import generate_password_hash
import psycopg2
import psycopg2.extras

user_bp = Blueprint('user', __name__)

@user_bp.route('/')
@role_required('system_admin')
def view_users():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("""
        SELECT u.user_id, u.full_name, u.email, u.role, t.teacher_id, t.phone
        FROM public.users u
        LEFT JOIN public.teachers t ON u.user_id = t.user_id
        ORDER BY u.full_name
    """)
    users = cursor.fetchall()
    cursor.close()
    return render_template('view_users.html', users=users)

@user_bp.route('/add', methods=['GET', 'POST'])
@role_required('system_admin')
def add_user():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        role = request.form.get('role')
        phone = request.form.get('phone')
        default_password = "password123"
        hashed_password = generate_password_hash(default_password)
        if not all([full_name, email, role]):
            flash("Full Name, Email, and Role are required fields.", "error")
            return render_template('add_user.html', form_data=request.form)
        if role == 'teacher' and not phone:
            flash("Phone number is required for the 'Teacher' role.", "error")
            return render_template('add_user.html', form_data=request.form)
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT user_id FROM public.users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("A user with this email address already exists.", "error")
            cursor.close()
            return render_template('add_user.html', form_data=request.form)
        
        cursor.execute(
            "INSERT INTO public.users (full_name, email, password, role) VALUES (%s, %s, %s, %s) RETURNING user_id",
            (full_name, email, hashed_password, role)
        )
        new_user_id = cursor.fetchone()['user_id']
        
        if role == 'teacher':
            cursor.execute("INSERT INTO public.teachers (user_id, phone) VALUES (%s, %s)", (new_user_id, phone))
        
        conn.commit()
        cursor.close()
        log_activity(f"Created new user: '{full_name}' with role '{role}'.")
        flash(f"User '{full_name}' created successfully.", "success")
        return redirect(url_for('user.view_users'))
    
    return render_template('add_user.html')

@user_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@role_required('system_admin')
def edit_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_details':
            full_name = request.form.get('full_name')
            email = request.form.get('email')
            role = request.form.get('role')
            phone = request.form.get('phone')

            if role == 'teacher' and not phone:
                flash("Phone number is required for the 'Teacher' role.", "error")
                cursor.close()
                return redirect(url_for('user.edit_user', user_id=user_id))

            cursor.execute("UPDATE public.users SET full_name = %s, email = %s, role = %s WHERE user_id = %s", (full_name, email, role, user_id))
            
            if role == 'teacher':
                cursor.execute("SELECT teacher_id FROM public.teachers WHERE user_id = %s", (user_id,))
                teacher_profile = cursor.fetchone()
                if teacher_profile:
                    cursor.execute("UPDATE public.teachers SET phone = %s WHERE user_id = %s", (phone, user_id))
                else:
                    cursor.execute("INSERT INTO public.teachers (user_id, phone) VALUES (%s, %s)", (user_id, phone))
            
            conn.commit()
            log_activity(f"Edited user details for '{full_name}' (ID: {user_id}).")
            flash("User details updated successfully.", "success")

        elif action == 'reset_password':
            default_password = "password123"
            hashed_password = generate_password_hash(default_password)
            cursor.execute("UPDATE public.users SET password = %s WHERE user_id = %s", (hashed_password, user_id))
            conn.commit()
            log_activity(f"Reset password for user ID: {user_id}.")
            flash("User's password has been reset to 'password123'.", "success")
        
        cursor.close()
        return redirect(url_for('user.edit_user', user_id=user_id))

    cursor.execute("""
        SELECT u.user_id, u.full_name, u.email, u.role, t.phone
        FROM public.users u
        LEFT JOIN public.teachers t ON u.user_id = t.user_id
        WHERE u.user_id = %s
    """, (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    if not user_data:
        flash("User not found.", "error")
        return redirect(url_for('user.view_users'))
        
    return render_template('edit_user.html', user=user_data)


@user_bp.route('/delete/<int:user_id>', methods=['POST'])
@role_required('system_admin')
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for('user.view_users'))
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT full_name FROM public.users WHERE user_id = %s", (user_id,))
    user_to_delete = cursor.fetchone()
    user_name = user_to_delete['full_name'] if user_to_delete else 'Unknown'
    
    cursor.execute("DELETE FROM public.teachers WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM public.users WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    log_activity(f"Deleted user: '{user_name}' (ID: {user_id}).")
    flash("User deleted successfully.", "success")
    return redirect(url_for('user.view_users'))