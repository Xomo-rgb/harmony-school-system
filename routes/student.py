from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db_connection
from utils import role_required, log_activity
from datetime import datetime, date
# --- CHANGES START HERE ---
import psycopg2
import psycopg2.extras
# --- CHANGES END HERE ---

student_bp = Blueprint('student', __name__)

@student_bp.route('/profile/<int:student_id>')
@role_required('teacher', 'school_admin', 'system_admin', 'accounts')
def profile(student_id):
    conn = get_db_connection()
    # Use the correct cursor factory for dictionary-like results
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
    student = cursor.fetchone()
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for('student.view_students'))
    cursor.execute("SELECT * FROM exam_results WHERE student_id = %s ORDER BY year DESC, term DESC, subject ASC", (student_id,))
    results = cursor.fetchall()
    cursor.execute("SELECT * FROM fee_payments WHERE student_id = %s ORDER BY payment_date DESC", (student_id,))
    payments = cursor.fetchall()
    cursor.close()
    return render_template('student_profile.html', student=student, results=results, payments=payments)


@student_bp.route('/register', methods=['GET', 'POST'])
@role_required('school_admin', 'system_admin')
def register_student():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        dob = request.form.get('dob')
        middle_name = request.form.get('middle_name')
        gender = request.form.get('gender')
        class_name = request.form.get('class_name')
        guardian_contact = request.form.get('guardian_contact')
        government_number = request.form.get('government_number', '').strip()
        special_needs = request.form.get('special_needs')
        address = request.form.get('address')
        enrollment_date = request.form.get('enrollment_date')

        if not all([first_name, last_name, dob, gender, class_name, guardian_contact, address, enrollment_date]):
            flash("Please fill out all required (*) fields.", "error")
            return render_template('register_student.html', form_data=request.form)

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if government_number:
            cursor.execute("SELECT student_id FROM students WHERE government_number = %s", (government_number,))
            if cursor.fetchone():
                flash(f"The government number '{government_number}' is already assigned to another student.", "error")
                cursor.close()
                return render_template('register_student.html', form_data=request.form)

        try:
            cursor.execute("SELECT MAX(student_id) as max_id FROM students")
            max_id = cursor.fetchone()['max_id'] or 0
            student_number = f"HS-2025-{str(max_id + 1).zfill(3)}"
            gov_num_to_insert = government_number if government_number else None

            insert_query = "INSERT INTO students (student_number, first_name, middle_name, last_name, dob, gender, class_name, guardian_contact, government_number, special_needs, address, enrollment_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            values = (student_number, first_name, middle_name, last_name, dob, gender, class_name, guardian_contact, gov_num_to_insert, special_needs, address, enrollment_date)
            cursor.execute(insert_query, values)
            conn.commit()

            log_activity(f"Registered new student: '{first_name} {last_name}' with number {student_number}.")
            flash(f"Student '{first_name} {last_name}' registered successfully.", "success")
            cursor.close()
            return redirect(url_for('student.view_students'))

        # --- CHANGE HERE: Catch the correct error type and code ---
        except psycopg2.Error as err:
            # PostgreSQL code for unique violation is '23505'
            if err.pgcode == '23505':
                 flash(f"A student with these details already exists.", "error")
            else:
                 flash(f"A database error occurred: {err}", "error")
            cursor.close()
            return render_template('register_student.html', form_data=request.form)

    return render_template('register_student.html')


@student_bp.route('/edit/<int:student_id>', methods=['GET', 'POST'])
@role_required('school_admin', 'system_admin')
def edit_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        middle_name = request.form['middle_name']
        dob = request.form['dob']
        gender = request.form['gender']
        class_name = request.form['class_name']
        guardian_contact = request.form['guardian_contact']
        government_number = request.form['government_number']
        special_needs = request.form['special_needs']
        address = request.form['address']
        enrollment_date = request.form['enrollment_date']
        update_query = "UPDATE students SET first_name=%s, middle_name=%s, last_name=%s, dob=%s, gender=%s, class_name=%s, guardian_contact=%s, government_number=%s, special_needs=%s, address=%s, enrollment_date=%s WHERE student_id=%s"
        values = (first_name, middle_name, last_name, dob, gender, class_name, guardian_contact, government_number, special_needs, address, enrollment_date, student_id)
        cursor.execute(update_query, values)
        conn.commit()
        log_activity(f"Edited student record for '{first_name} {last_name}' (ID: {student_id}).")
        flash("Student information updated successfully.", "success")
        cursor.close()
        return redirect(url_for('student.view_students'))
    
    cursor.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
    student = cursor.fetchone()
    cursor.close()
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for('student.view_students'))
    if student.get('dob'):
        student['dob'] = student['dob'].strftime('%Y-%m-%d')
    if student.get('enrollment_date'):
        student['enrollment_date'] = student['enrollment_date'].strftime('%Y-%m-%d')
    return render_template('edit_student.html', student=student)


@student_bp.route('/delete/<int:student_id>', methods=['POST'])
@role_required('school_admin', 'system_admin')
def delete_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = %s", (student_id,))
    student_to_delete = cursor.fetchone()
    if not student_to_delete:
        flash("Student not found.", "error")
        cursor.close()
        return redirect(url_for('student.view_students'))
    student_name = f"{student_to_delete['first_name']} {student_to_delete['last_name']}"
    cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
    conn.commit()
    log_activity(f"Deleted student record for '{student_name}' (ID: {student_id}).")
    flash("Student deleted successfully.", "success")
    cursor.close()
    return redirect(url_for('student.view_students'))


@student_bp.route('/')
@role_required('teacher', 'school_admin', 'system_admin', 'accounts')
def view_students():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM students ORDER BY last_name, first_name")
    students = cursor.fetchall()
    cursor.close()
    return render_template('view_students.html', students=students)


@student_bp.route('/filter', methods=['POST'])
@role_required('teacher', 'school_admin', 'system_admin', 'accounts')
def filter_students():
    selected_class = request.form.get('class_name')
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if selected_class:
        cursor.execute("SELECT * FROM students WHERE class_name = %s ORDER BY last_name, first_name", (selected_class,))
    else:
        cursor.execute("SELECT * FROM students ORDER BY last_name, first_name")
    students = cursor.fetchall()
    cursor.close()
    students_list = []
    # Convert Row objects to plain dictionaries for JSON serialization
    for s in students:
        s_dict = dict(s)
        s_dict['dob'] = s_dict['dob'].strftime('%Y-%m-%d') if s_dict.get('dob') else None
        s_dict['enrollment_date'] = s_dict['enrollment_date'].strftime('%Y-%m-%d') if s_dict.get('enrollment_date') else None
        s_dict['full_name'] = f"{s_dict['first_name']} {s_dict.get('middle_name') or ''} {s_dict['last_name']}".replace('  ', ' ')
        students_list.append(s_dict)
    return jsonify({"students": students_list})