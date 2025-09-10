from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from db import get_db_connection
from utils import role_required, log_activity

admin_bp = Blueprint('admin', __name__)

# --- View Logs ---
@admin_bp.route('/logs')
@role_required('system_admin')
def view_logs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_full_name, action, timestamp FROM activity_logs ORDER BY timestamp DESC")
    logs = cursor.fetchall()
    return render_template('view_logs.html', logs=logs)

# --- Fee Payment Functions ---
def _get_filtered_fee_payments(selected_year, selected_term, selected_class):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT fp.payment_id, s.student_number, s.first_name, s.middle_name, s.last_name, fp.amount_paid, fp.payment_date, fp.term, fp.academic_year, s.class_name FROM fee_payments fp JOIN students s ON fp.student_id = s.student_id"
    filters = []
    params = []
    if selected_year:
        filters.append("fp.academic_year = %s")
        params.append(selected_year)
    if selected_term:
        filters.append("fp.term = %s")
        params.append(selected_term)
    if selected_class:
        filters.append("s.class_name = %s")
        params.append(selected_class)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY fp.payment_date DESC"
    cursor.execute(query, tuple(params))
    return cursor.fetchall()

@admin_bp.route('/fee_payment_form')
@role_required('accounts')
def fee_payment_form():
    return render_template('record_payment.html')

@admin_bp.route('/submit_fee', methods=['POST'])
@role_required('accounts')
def submit_fee():
    student_number = request.form.get('student_number')
    amount_paid = request.form.get('amount_paid')
    payment_date = request.form.get('payment_date')
    term = request.form.get('term')
    academic_year = request.form.get('academic_year')
    if not all([student_number, amount_paid, payment_date, term, academic_year]):
        flash("Please fill out all fields.", "error")
        return redirect(url_for('admin.fee_payment_form'))
    try:
        amount_paid = float(amount_paid)
    except ValueError:
        flash("Invalid amount entered. Please use numbers only.", "error")
        return redirect(url_for('admin.fee_payment_form'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT student_id, first_name, last_name FROM students WHERE student_number = %s", (student_number,))
    student = cursor.fetchone()
    if not student:
        flash("Student number not found.", "error")
        return redirect(url_for('admin.fee_payment_form'))
    student_id = student['student_id']
    student_name = f"{student['first_name']} {student.get('last_name', '')}".strip()
    cursor.execute("INSERT INTO fee_payments (student_id, amount_paid, payment_date, term, academic_year) VALUES (%s, %s, %s, %s, %s)", (student_id, amount_paid, payment_date, term, academic_year))
    conn.commit()
    log_activity(f"Recorded fee payment of {amount_paid} for student '{student_name}' ({student_number}).")
    flash("Fee payment recorded successfully.", "success")
    return redirect(url_for('admin.fee_payment_form'))

@admin_bp.route('/view_fee_payments')
@role_required('system_admin', 'school_admin', 'accounts')
def view_fee_payments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT academic_year FROM fee_payments ORDER BY academic_year DESC")
    academic_years = [row['academic_year'] for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT term FROM fee_payments ORDER BY term")
    terms = [row['term'] for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT class_name FROM classes ORDER BY class_name")
    classes = [row['class_name'] for row in cursor.fetchall()]
    return render_template('view_fee_payments.html', academic_years=academic_years, terms=terms, classes=classes)

@admin_bp.route('/filter_fee_payments', methods=['POST'])
@role_required('system_admin', 'school_admin', 'accounts')
def filter_fee_payments():
    selected_year = request.form.get('academic_year')
    selected_term = request.form.get('term')
    selected_class = request.form.get('class_name')
    results = _get_filtered_fee_payments(selected_year, selected_term, selected_class)
    payments = []
    for r in results:
        payments.append({"payment_id": r["payment_id"], "student_number": r["student_number"], "full_name": f"{r['first_name']} {r.get('middle_name') or ''} {r['last_name']}".replace('  ', ' '), "amount_paid": r["amount_paid"], "payment_date": r["payment_date"].strftime("%Y-%m-%d"), "term": r["term"], "academic_year": r["academic_year"], "class_name": r["class_name"]})
    return jsonify({"payments": payments})

@admin_bp.route('/edit_fee/<int:payment_id>', methods=['GET', 'POST'])
@role_required('accounts')
def edit_fee(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        amount_paid = request.form.get('amount_paid')
        payment_date = request.form.get('payment_date')
        term = request.form.get('term')
        academic_year = request.form.get('academic_year')
        if not all([amount_paid, payment_date, term, academic_year]):
            flash("Please fill out all fields.", "error")
            return redirect(url_for('admin.edit_fee', payment_id=payment_id))
        try:
            amount_paid = float(amount_paid)
        except ValueError:
            flash("Invalid amount entered.", "error")
            return redirect(url_for('admin.edit_fee', payment_id=payment_id))
        cursor.execute("UPDATE fee_payments SET amount_paid = %s, payment_date = %s, term = %s, academic_year = %s WHERE payment_id = %s", (amount_paid, payment_date, term, academic_year, payment_id))
        conn.commit()
        log_activity(f"Edited fee payment record (ID: {payment_id}).")
        flash("Fee payment updated successfully.", "success")
        return redirect(url_for('admin.view_fee_payments'))
    cursor.execute("SELECT fp.*, s.student_number, s.first_name, s.middle_name, s.last_name FROM fee_payments fp JOIN students s ON fp.student_id = s.student_id WHERE fp.payment_id = %s", (payment_id,))
    payment = cursor.fetchone()
    if not payment:
        flash("Fee payment record not found.", "error")
        return redirect(url_for('admin.view_fee_payments'))
    if payment['payment_date']:
        payment['payment_date'] = payment['payment_date'].strftime('%Y-%m-%d')
    return render_template('edit_fee.html', payment=payment)

@admin_bp.route('/delete_fee/<int:payment_id>', methods=['POST'])
@role_required('accounts')
def delete_fee(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT s.student_number FROM fee_payments fp JOIN students s ON fp.student_id = s.student_id WHERE payment_id = %s", (payment_id,))
    payment_to_delete = cursor.fetchone()
    if not payment_to_delete:
        flash("Payment record not found.", "error")
        return redirect(url_for('admin.view_fee_payments'))
    cursor.execute("DELETE FROM fee_payments WHERE payment_id = %s", (payment_id,))
    conn.commit()
    student_number = payment_to_delete['student_number']
    log_activity(f"Deleted fee payment record (ID: {payment_id}) for student {student_number}.")
    flash("Fee payment deleted successfully.", "success")
    return redirect(url_for('admin.view_fee_payments'))

# --- Dashboards & Unauthorized Page ---
@admin_bp.route('/unauthorized')
def unauthorized():
    return render_template('unauthorized.html'), 403

@admin_bp.route('/system_admin_dashboard')
@role_required('system_admin')
def system_admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM students")
    total_students = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'teacher'")
    total_teachers = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(DISTINCT class_name) as count FROM classes")
    total_classes = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    cursor.execute("SELECT full_name as user, 'User Created' as action, role as timestamp FROM users ORDER BY user_id DESC LIMIT 5")
    recent_activities = cursor.fetchall()
    return render_template('system_admin_dashboard.html', total_students=total_students, total_teachers=total_teachers, total_classes=total_classes, total_users=total_users, recent_activities=recent_activities)

@admin_bp.route('/accounts_dashboard', endpoint='accounts_dashboard')
@role_required('accounts')
def accounts_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(payment_id) as count FROM fee_payments")
    payment_count = cursor.fetchone()['count']
    cursor.execute("SELECT SUM(amount_paid) as total FROM fee_payments")
    total_collected = cursor.fetchone()['total'] or 0
    return render_template('accounts_dashboard.html', payment_count=payment_count, total_collected=total_collected)

@admin_bp.route('/school_admin_dashboard', endpoint='school_admin_dashboard')
@role_required('school_admin')
def school_admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM students")
    total_students = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'teacher'")
    total_teachers = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(DISTINCT class_name) as count FROM classes")
    total_classes = cursor.fetchone()['count']
    return render_template('school_admin_dashboard.html', total_students=total_students, total_teachers=total_teachers, total_classes=total_classes)

# --- AJAX ENDPOINTS FOR DASHBOARD CHARTS ---
@admin_bp.route('/data/students_per_class')
@role_required('system_admin')
def get_students_per_class_data():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT class_name, COUNT(student_id) as student_count FROM students GROUP BY class_name ORDER BY class_name;")
    data = cursor.fetchall()
    labels = [row['class_name'] for row in data]
    values = [row['student_count'] for row in data]
    return jsonify({'labels': labels, 'values': values})

@admin_bp.route('/data/users_by_role')
@role_required('system_admin')
def get_users_by_role_data():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role, COUNT(user_id) as user_count FROM users GROUP BY role ORDER BY role;")
    data = cursor.fetchall()
    labels = [row['role'].replace('_', ' ').title() for row in data]
    values = [row['user_count'] for row in data]
    return jsonify({'labels': labels, 'values': values})