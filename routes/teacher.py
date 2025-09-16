from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db_connection
from utils import role_required, log_activity
from datetime import datetime
# --- CHANGES START HERE ---
import psycopg2
import psycopg2.extras
# --- CHANGES END HERE ---

teacher_bp = Blueprint('teacher', __name__)

# --- Helper functions ---
def get_teacher_assigned_classes(user_id):
    conn = get_db_connection()
    # Use the correct cursor factory
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query = """
        SELECT DISTINCT c.class_name
        FROM teacher_assignments ta
        JOIN teachers t ON ta.teacher_id = t.teacher_id
        JOIN classes c ON ta.class_id = c.class_id
        WHERE t.user_id = %s
    """
    cursor.execute(query, (user_id,))
    assigned_classes = [row['class_name'] for row in cursor.fetchall()]
    cursor.close()
    return assigned_classes

def calculate_grade(final_score):
    if not isinstance(final_score, (int, float)): return 'N/A'
    if final_score >= 90: return 'A+'
    elif final_score >= 80: return 'A'
    elif final_score >= 70: return 'B'
    elif final_score >= 60: return 'C'
    elif final_score >= 50: return 'D'
    elif final_score >= 40: return 'E'
    else: return 'F'

# --- Teacher Dashboard ---
@teacher_bp.route('/dashboard', endpoint='teacher_dashboard')
@role_required('teacher')
def teacher_dashboard():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    assigned_classes = get_teacher_assigned_classes(user_id)
    
    total_students = 0
    if assigned_classes:
        placeholders = ', '.join(['%s'] * len(assigned_classes))
        query = f"SELECT COUNT(student_id) as count FROM students WHERE class_name IN ({placeholders})"
        cursor.execute(query, tuple(assigned_classes))
        result = cursor.fetchone()
        if result:
            total_students = result['count']
    
    cursor.close()
    return render_template('teacher_dashboard.html', 
                           class_count=len(assigned_classes), 
                           student_count=total_students)

# --- Enter Exam Results ---
@teacher_bp.route('/enter_results', methods=['GET', 'POST'])
@role_required('teacher')
def enter_results():
    user_id = session.get('user_id')
    assigned_classes = get_teacher_assigned_classes(user_id)
    if not assigned_classes:
        flash("You are not currently assigned to any classes. Please contact an administrator.", "warning")
        return render_template('enter_results.html', classes=[])

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject = request.form.get('subject')
        term = request.form.get('term')
        academic_year = request.form.get('academic_year')
        
        try:
            ca_score = int(float(request.form['ca_score']))
            midterm_score = int(float(request.form['midterm_score']))
            final_exam_score = int(float(request.form['final_exam_score']))
        except (ValueError, TypeError):
            flash("Invalid score entered. Please use numbers only.", "error")
            return redirect(url_for('teacher.enter_results'))

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute(
            "SELECT result_id FROM exam_results WHERE student_id = %s AND subject = %s AND term = %s AND year = %s",
            (student_id, subject, term, academic_year)
        )
        if cursor.fetchone():
            flash(f"A result for {subject} has already been entered for this student in this term. Please use 'View Results' to edit it.", "error")
            cursor.close()
            return redirect(url_for('teacher.enter_results'))

        final_score = round((ca_score + midterm_score + final_exam_score) / 3)
        grade = calculate_grade(final_score)
        
        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()
        student_name = f"{student['first_name']} {student['last_name']}" if student else "Unknown Student"

        cursor.execute("""
            INSERT INTO exam_results
            (student_id, subject, ca_score, midterm_score, final_exam_score, final_score, grade, term, year)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (student_id, subject, ca_score, midterm_score, final_exam_score, final_score, grade, term, academic_year))
        conn.commit()
        cursor.close()

        log_activity(f"Entered exam result for '{student_name}' in '{subject}' for {term}, {academic_year}.")
        flash(f"Result for {subject} recorded successfully! Final score: {final_score}, Grade: {grade}", "success")
        return redirect(url_for('teacher.enter_results'))

    return render_template('enter_results.html', classes=assigned_classes)

# --- View Results Page ---
@teacher_bp.route('/view_results')
@role_required('teacher', 'system_admin', 'school_admin')
def view_results():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    user_id = session.get('user_id')
    if session.get('role') == 'teacher':
        cursor.execute("""
            SELECT DISTINCT c.class_id, c.class_name
            FROM teacher_assignments ta
            JOIN teachers t ON ta.teacher_id = t.teacher_id
            JOIN classes c ON ta.class_id = c.class_id
            WHERE t.user_id = %s
            ORDER BY c.class_id
        """, (user_id,))
    else:
        cursor.execute("SELECT class_id, class_name FROM classes ORDER BY class_id")
    all_classes = cursor.fetchall()
    cursor.close()
    return render_template('view_results.html', classes=all_classes)

# --- Edit/Delete Functions ---
@teacher_bp.route('/edit_result/<int:result_id>', methods=['GET', 'POST'])
@role_required('teacher', 'school_admin', 'system_admin')
def edit_result(result_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        try:
            ca_score = int(float(request.form['ca_score']))
            midterm_score = int(float(request.form['midterm_score']))
            final_exam_score = int(float(request.form['final_exam_score']))
        except (ValueError, TypeError):
            flash("Invalid score entered. Please use numbers only.", "error")
            return redirect(url_for('teacher.edit_result', result_id=result_id))
        final_score = round((ca_score + midterm_score + final_exam_score) / 3)
        grade = calculate_grade(final_score)
        cursor.execute("SELECT s.first_name, s.last_name, er.subject FROM exam_results er JOIN students s ON er.student_id = s.student_id WHERE er.result_id = %s", (result_id,))
        result_details = cursor.fetchone()
        cursor.execute("UPDATE exam_results SET ca_score = %s, midterm_score = %s, final_exam_score = %s, final_score = %s, grade = %s WHERE result_id = %s", (ca_score, midterm_score, final_exam_score, final_score, grade, result_id))
        conn.commit()
        cursor.close()
        if result_details:
            student_name = f"{result_details['first_name']} {result_details['last_name']}"
            subject = result_details['subject']
            log_activity(f"Edited exam result for '{student_name}' in '{subject}'.")
        flash("Result updated successfully.", "success")
        return redirect(url_for('teacher.view_results'))
    
    cursor.execute("SELECT er.*, s.first_name, s.last_name, s.class_name FROM exam_results er JOIN students s ON er.student_id = s.student_id WHERE er.result_id = %s", (result_id,))
    result = cursor.fetchone()
    cursor.close()
    if not result:
        flash("Exam result not found.", "error")
        return redirect(url_for('teacher.view_results'))
    if session.get('role') == 'teacher':
        user_id = session.get('user_id')
        assigned_classes = get_teacher_assigned_classes(user_id)
        if result['class_name'] not in assigned_classes:
            flash("You do not have permission to edit results for this class.", "error")
            return redirect(url_for('teacher.view_results'))
    return render_template('edit_result.html', result=result)

@teacher_bp.route('/delete_result/<int:result_id>', methods=['POST'])
@role_required('teacher', 'school_admin', 'system_admin')
def delete_result(result_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT s.class_name, s.first_name, s.last_name, er.subject FROM exam_results er JOIN students s ON er.student_id = s.student_id WHERE er.result_id = %s", (result_id,))
    result_to_delete = cursor.fetchone()
    if not result_to_delete:
        flash("Result not found.", "error")
        cursor.close()
        return redirect(url_for('teacher.view_results'))
    if session.get('role') == 'teacher':
        user_id = session.get('user_id')
        assigned_classes = get_teacher_assigned_classes(user_id)
        if result_to_delete['class_name'] not in assigned_classes:
            flash("You do not have permission to delete results for this class.", "error")
            cursor.close()
            return redirect(url_for('teacher.view_results'))
    cursor.execute("DELETE FROM exam_results WHERE result_id = %s", (result_id,))
    conn.commit()
    cursor.close()
    student_name = f"{result_to_delete['first_name']} {result_to_delete['last_name']}"
    subject = result_to_delete['subject']
    log_activity(f"Deleted exam result for '{student_name}' in '{subject}'.")
    flash("Exam result deleted successfully.", "success")
    return redirect(url_for('teacher.view_results'))

# --- AJAX ENDPOINTS ---
@teacher_bp.route('/get_students_for_class_list', methods=['POST'])
@role_required('teacher')
def get_students_for_class_list():
    class_name = request.form.get('class_name')
    if not class_name: return jsonify([])
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if session['role'] == 'teacher':
        user_id = session['user_id']
        assigned_classes = get_teacher_assigned_classes(user_id)
        if class_name not in assigned_classes:
            cursor.close()
            return jsonify({'error': 'Unauthorized'}), 403
    cursor.execute("SELECT student_id, first_name, last_name, student_number FROM students WHERE class_name = %s ORDER BY last_name, first_name", (class_name,))
    students = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    return jsonify(students)

@teacher_bp.route('/get_students_for_results', methods=['POST'])
@role_required('teacher', 'school_admin', 'system_admin')
def get_students_for_results():
    class_name = request.form.get('class_name')
    if not class_name: return jsonify([])
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if session['role'] == 'teacher':
        user_id = session['user_id']
        assigned_classes = get_teacher_assigned_classes(user_id)
        if class_name not in assigned_classes:
            cursor.close()
            return jsonify({'error': 'Unauthorized'}), 403
    cursor.execute("SELECT student_id, first_name, last_name, student_number FROM students WHERE class_name = %s ORDER BY last_name, first_name", (class_name,))
    students = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    return jsonify(students)

@teacher_bp.route('/get_student_report_card', methods=['POST'])
@role_required('teacher', 'school_admin', 'system_admin')
def get_student_report_card():
    student_id = request.form.get('student_id')
    term = request.form.get('term')
    year = request.form.get('year')
    if not all([student_id, term, year]):
        return jsonify({'error': 'Missing required parameters.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT student_id, first_name, last_name, class_name FROM students WHERE student_id = %s", (student_id,))
    student_info = dict(cursor.fetchone())
    cursor.execute("SELECT * FROM exam_results WHERE student_id = %s AND term = %s AND year = %s ORDER BY subject", (student_id, term, year))
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    report_data = {'student': student_info, 'results': results}
    return jsonify(report_data)

@teacher_bp.route('/get_subject_report', methods=['POST'])
@role_required('teacher', 'school_admin', 'system_admin')
def get_subject_report():
    class_name = request.form.get('class_name')
    subject = request.form.get('subject')
    term = request.form.get('term')
    year = request.form.get('year')
    if not all([class_name, subject, term, year]):
        return jsonify({'error': 'Missing required parameters.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if session['role'] == 'teacher':
        user_id = session['user_id']
        assigned_classes = get_teacher_assigned_classes(user_id)
        if class_name not in assigned_classes:
            cursor.close()
            return jsonify({'error': 'Unauthorized'}), 403
    cursor.execute("SELECT s.first_name, s.last_name, s.student_number, er.final_score, er.grade FROM exam_results er JOIN students s ON er.student_id = s.student_id WHERE s.class_name = %s AND er.subject = %s AND er.term = %s AND er.year = %s ORDER BY s.last_name, s.first_name", (class_name, subject, term, year))
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    return jsonify(results)