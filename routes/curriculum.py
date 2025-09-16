from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from db import get_db_connection
from utils import role_required, log_activity
# --- CHANGES START HERE ---
import psycopg2
import psycopg2.extras
# --- CHANGES END HERE ---

curriculum_bp = Blueprint('curriculum', __name__)

@curriculum_bp.route('/')
@role_required('system_admin', 'school_admin')
def manage():
    conn = get_db_connection()
    # Use the correct cursor factory
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT class_id, class_name FROM classes ORDER BY class_id")
    classes_rows = cursor.fetchall()
    
    # Convert Row objects to dictionaries to make them mutable
    classes = [dict(c) for c in classes_rows]

    for c in classes:
        cursor.execute("""
            SELECT s.subject_name, curr.curriculum_id
            FROM curriculum curr
            JOIN subjects s ON curr.subject_id = s.subject_id
            WHERE curr.class_id = %s
            ORDER BY s.subject_name
        """, (c['class_id'],))
        c['subjects'] = cursor.fetchall()
        
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    all_subjects = cursor.fetchall()
    cursor.close()
    return render_template('manage_curriculum.html', 
                           classes=classes, 
                           all_subjects=all_subjects)

@curriculum_bp.route('/add', methods=['POST'])
@role_required('system_admin', 'school_admin')
def add_subject_to_class():
    class_id = request.form.get('class_id')
    subject_id = request.form.get('subject_id')

    if not class_id or not subject_id:
        flash("Please select both a class and a subject to add.", "error")
        return redirect(url_for('curriculum.manage'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO curriculum (class_id, subject_id) VALUES (%s, %s)",
            (class_id, subject_id)
        )
        conn.commit()
        log_activity(f"Added subject ID {subject_id} to class ID {class_id} in curriculum.")
        flash("Subject added to curriculum successfully.", "success")
    # --- CHANGE HERE: Catch the correct error type and code ---
    except psycopg2.Error as err:
        # PostgreSQL code for unique violation is '23505'
        if err.pgcode == '23505':
            flash("This subject is already part of this class's curriculum.", "warning")
        else:
            flash(f"A database error occurred: {err}", "error")
    finally:
        cursor.close()
    
    return redirect(url_for('curriculum.manage'))

@curriculum_bp.route('/remove/<int:curriculum_id>', methods=['POST'])
@role_required('system_admin', 'school_admin')
def remove_subject_from_class(curriculum_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM curriculum WHERE curriculum_id = %s", (curriculum_id,))
    conn.commit()
    cursor.close()
    log_activity(f"Removed curriculum link ID {curriculum_id}.")
    flash("Subject removed from curriculum successfully.", "success")
    return redirect(url_for('curriculum.manage'))

@curriculum_bp.route('/get_subjects_for_class/<int:class_id>')
@role_required('system_admin', 'school_admin')
def get_subjects_for_class(class_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("""
        SELECT s.subject_id, s.subject_name
        FROM curriculum c
        JOIN subjects s ON c.subject_id = s.subject_id
        WHERE c.class_id = %s
        ORDER BY s.subject_name
    """, (class_id,))
    # Convert to list of dicts for reliable JSON conversion
    subjects = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    return jsonify(subjects)