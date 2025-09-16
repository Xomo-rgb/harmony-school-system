from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_db_connection
from utils import role_required, log_activity
# --- CHANGES START HERE ---
import psycopg2
import psycopg2.extras
# --- CHANGES END HERE ---

assignment_bp = Blueprint('assignment', __name__)

@assignment_bp.route('/manage/<int:teacher_user_id>')
@role_required('system_admin', 'school_admin')
def manage(teacher_user_id):
    conn = get_db_connection()
    # Use the correct cursor factory
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT user_id, full_name FROM users WHERE user_id = %s AND role = 'teacher'", (teacher_user_id,))
    teacher = cursor.fetchone()
    if not teacher:
        flash("Teacher not found.", "error")
        cursor.close()
        return redirect(url_for('user.view_users'))
    cursor.execute("""
        SELECT ta.assignment_id, c.class_name, s.subject_name
        FROM teacher_assignments ta
        JOIN subjects s ON ta.subject_id = s.subject_id
        JOIN teachers t ON ta.teacher_id = t.teacher_id
        JOIN classes c ON ta.class_id = c.class_id
        WHERE t.user_id = %s
        ORDER BY c.class_name, s.subject_name
    """, (teacher_user_id,))
    current_assignments = cursor.fetchall()
    cursor.execute("SELECT class_id, class_name FROM classes ORDER BY class_name")
    all_classes = cursor.fetchall()
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    all_subjects = cursor.fetchall()
    cursor.close()
    return render_template('manage_assignments.html',
                           teacher=teacher,
                           current_assignments=current_assignments,
                           all_classes=all_classes,
                           all_subjects=all_subjects)

@assignment_bp.route('/add/<int:teacher_user_id>', methods=['POST'])
@role_required('system_admin', 'school_admin')
def add_assignment(teacher_user_id):
    class_id = request.form.get('class_id')
    subject_id = request.form.get('subject_id')

    if not class_id or not subject_id:
        flash("Please select both a class and a subject.", "error")
        return redirect(url_for('assignment.manage', teacher_user_id=teacher_user_id))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT teacher_id, u.full_name FROM teachers t JOIN users u ON t.user_id = u.user_id WHERE t.user_id = %s", (teacher_user_id,))
    teacher = cursor.fetchone()
    if not teacher:
        flash("Teacher profile not found.", "error")
        cursor.close()
        return redirect(url_for('user.view_users'))
    teacher_id = teacher['teacher_id']
    teacher_name = teacher['full_name']

    cursor.execute("SELECT class_name FROM classes WHERE class_id = %s", (class_id,))
    class_obj = cursor.fetchone()
    class_name = class_obj['class_name'] if class_obj else 'Unknown Class'

    cursor.execute("SELECT subject_name FROM subjects WHERE subject_id = %s", (subject_id,))
    subject_obj = cursor.fetchone()
    subject_name = subject_obj['subject_name'] if subject_obj else 'Unknown Subject'

    cursor.execute(
        "SELECT assignment_id FROM teacher_assignments WHERE teacher_id = %s AND class_id = %s AND subject_id = %s",
        (teacher_id, class_id, subject_id)
    )
    if cursor.fetchone():
        flash("This teacher is already assigned to that class and subject.", "warning")
        cursor.close()
        return redirect(url_for('assignment.manage', teacher_user_id=teacher_user_id))

    cursor.execute(
        "INSERT INTO teacher_assignments (teacher_id, class_id, subject_id) VALUES (%s, %s, %s)",
        (teacher_id, class_id, subject_id)
    )
    conn.commit()
    cursor.close()

    log_activity(f"Assigned '{teacher_name}' to teach '{subject_name}' in '{class_name}'.")
    flash("Assignment added successfully.", "success")
    return redirect(url_for('assignment.manage', teacher_user_id=teacher_user_id))

@assignment_bp.route('/remove/<int:assignment_id>', methods=['POST'])
@role_required('system_admin', 'school_admin')
def remove_assignment(assignment_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("""
        SELECT t.user_id, u.full_name, c.class_name, s.subject_name
        FROM teacher_assignments ta
        JOIN teachers t ON ta.teacher_id = t.teacher_id
        JOIN users u ON t.user_id = u.user_id
        JOIN classes c ON ta.class_id = c.class_id
        JOIN subjects s ON ta.subject_id = s.subject_id
        WHERE ta.assignment_id = %s
    """, (assignment_id,))
    assignment_to_delete = cursor.fetchone()

    cursor.execute("DELETE FROM teacher_assignments WHERE assignment_id = %s", (assignment_id,))
    conn.commit()
    cursor.close()
    flash("Assignment removed successfully.", "success")
    
    if assignment_to_delete:
        teacher_name = assignment_to_delete['full_name']
        class_name = assignment_to_delete['class_name']
        subject_name = assignment_to_delete['subject_name']
        log_activity(f"Removed assignment for '{teacher_name}' to teach '{subject_name}' in '{class_name}'.")
        return redirect(url_for('assignment.manage', teacher_user_id=assignment_to_delete['user_id']))
    
    return redirect(url_for('user.view_users'))