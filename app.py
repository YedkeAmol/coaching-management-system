import os
from functools import wraps
from datetime import datetime, timezone
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
    Response,
    send_file
)
from config import Config
from database import (
    get_db_manager,
    get_db,
    format_inr,
    format_date_indian,
    paise_to_rupees,
    rupees_to_paise
)
from services.auth_service import AuthService
from services.student_service import StudentService
from services.batch_service import BatchService
from services.fee_service import FeeService
from services.payment_service import PaymentService
from services.report_service import ReportService
from services.settings_service import SettingsService

app = Flask(__name__)
app.config.from_object(Config)

# Register custom Jinja template filters
@app.template_filter("inr")
def inr_filter(value):
    return format_inr(value)

@app.template_filter("date_in")
def date_in_filter(value):
    return format_date_indian(value)

@app.context_processor
def inject_global_data():
    db_mgr = get_db_manager()
    settings = SettingsService.get_settings()
    user_info = None
    if "user_id" in session:
        user_info = {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "full_name": session.get("full_name", "Admin")
        }
    return {
        "current_user": user_info,
        "app_settings": settings,
        "is_db_mock": db_mgr.is_mock,
        "current_year": datetime.now().year,
        "current_month_str": datetime.now().strftime("%Y-%m"),
        "today_date": datetime.now().strftime("%Y-%m-%d")
    }

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Authentication required"}), 401
            return redirect(url_for("login_page", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# =========================================================================
# Authentication Routes
# =========================================================================

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard_page"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = AuthService.authenticate(username, password)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash("Welcome back!", "success")
            next_url = request.args.get("next") or url_for("dashboard_page")
            return redirect(next_url)
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login_page"))


# =========================================================================
# Web UI Pages
# =========================================================================

@app.route("/")
@login_required
def root():
    return redirect(url_for("dashboard_page"))

@app.route("/dashboard")
@login_required
def dashboard_page():
    dashboard_data = ReportService.get_dashboard_data()
    batches = BatchService.get_all_batches(active_only=True)
    return render_template("dashboard.html", data=dashboard_data, batches=batches)

@app.route("/students")
@login_required
def students_page():
    batches = BatchService.get_all_batches(active_only=True)
    courses = BatchService.get_all_courses(active_only=True)
    return render_template("students.html", batches=batches, courses=courses)

@app.route("/students/<student_id>")
@login_required
def student_profile_page(student_id):
    student = StudentService.get_student_by_id(student_id)
    if not student:
        flash(f"Student '{student_id}' not found.", "error")
        return redirect(url_for("students_page"))

    fee_summary = FeeService.get_student_fee_summary(student_id)
    batches = BatchService.get_all_batches(active_only=True)
    return render_template("student_profile.html", student=student, fee_summary=fee_summary, batches=batches)

@app.route("/batches")
@login_required
def batches_page():
    batches = BatchService.get_all_batches(active_only=False)
    courses = BatchService.get_all_courses(active_only=False)
    return render_template("batches.html", batches=batches, courses=courses)

@app.route("/fees")
@login_required
def fees_page():
    batches = BatchService.get_all_batches(active_only=True)
    current_ym = datetime.now().strftime("%Y-%m")
    return render_template("fees.html", batches=batches, current_month=current_ym)

@app.route("/payments")
@login_required
def payments_page():
    return render_template("payments.html")

@app.route("/pending-fees")
@login_required
def pending_fees_page():
    batches = BatchService.get_all_batches(active_only=True)
    return render_template("pending_fees.html", batches=batches)

@app.route("/reports")
@login_required
def reports_page():
    batches = BatchService.get_all_batches(active_only=True)
    return render_template("reports.html", batches=batches)

@app.route("/settings")
@login_required
def settings_page():
    settings = SettingsService.get_settings()
    return render_template("settings.html", settings=settings)

@app.route("/receipt/<receipt_no_or_id>")
@login_required
def print_receipt_page(receipt_no_or_id):
    receipt = PaymentService.get_receipt_data(receipt_no_or_id)
    if not receipt:
        flash("Receipt record not found.", "error")
        return redirect(url_for("payments_page"))
    return render_template("receipt_print.html", receipt=receipt)


# =========================================================================
# REST API Endpoints
# =========================================================================

# --- Dashboard API ---
@app.route("/api/dashboard", methods=["GET"])
@login_required
def api_dashboard():
    try:
        data = ReportService.get_dashboard_data()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Students API ---
@app.route("/api/students", methods=["GET"])
@login_required
def api_get_students():
    search = request.args.get("search", "")
    batch_id = request.args.get("batch_id", "")
    status = request.args.get("status", "Active")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    sort_by = request.args.get("sort_by", "student_id")
    sort_order = int(request.args.get("sort_order", 1))

    result = StudentService.get_students(
        search=search,
        batch_id=batch_id,
        status=status,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return jsonify({"success": True, "data": result})

@app.route("/api/students", methods=["POST"])
@login_required
def api_create_student():
    data = request.get_json() or {}
    success, msg, student = StudentService.create_student(data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg, "data": student}), 201

@app.route("/api/students/<student_id>", methods=["GET"])
@login_required
def api_get_student(student_id):
    student = StudentService.get_student_by_id(student_id)
    if not student:
        return jsonify({"success": False, "error": "Student not found"}), 404
    return jsonify({"success": True, "data": student})

@app.route("/api/students/<student_id>", methods=["PUT"])
@login_required
def api_update_student(student_id):
    data = request.get_json() or {}
    success, msg = StudentService.update_student(student_id, data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg})

@app.route("/api/students/<student_id>", methods=["DELETE"])
@login_required
def api_delete_student(student_id):
    success, msg = StudentService.delete_or_archive_student(student_id)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg})

@app.route("/api/students/<student_id>/fees", methods=["GET"])
@login_required
def api_get_student_fees(student_id):
    summary = FeeService.get_student_fee_summary(student_id)
    if not summary:
        return jsonify({"success": False, "error": "Student not found"}), 404
    return jsonify({"success": True, "data": summary})

# --- Batches and Courses API ---
@app.route("/api/batches", methods=["GET"])
@login_required
def api_get_batches():
    active_only = request.args.get("active_only", "false").lower() == "true"
    batches = BatchService.get_all_batches(active_only=active_only)
    return jsonify({"success": True, "data": batches})

@app.route("/api/batches", methods=["POST"])
@login_required
def api_create_batch():
    data = request.get_json() or {}
    success, msg, batch = BatchService.create_batch(data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg, "data": batch}), 201

@app.route("/api/batches/<batch_id>", methods=["PUT"])
@login_required
def api_update_batch(batch_id):
    data = request.get_json() or {}
    success, msg = BatchService.update_batch(batch_id, data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg})

@app.route("/api/courses", methods=["GET"])
@login_required
def api_get_courses():
    courses = BatchService.get_all_courses(active_only=False)
    return jsonify({"success": True, "data": courses})

@app.route("/api/courses", methods=["POST"])
@login_required
def api_create_course():
    data = request.get_json() or {}
    success, msg, course = BatchService.create_course(data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg, "data": course}), 201

@app.route("/api/courses/<course_id>", methods=["PUT"])
@login_required
def api_update_course(course_id):
    data = request.get_json() or {}
    success, msg = BatchService.update_course(course_id, data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg})

# --- Fees API ---
@app.route("/api/fees/monthly", methods=["GET"])
@login_required
def api_get_monthly_fees():
    month_year = request.args.get("month", datetime.now().strftime("%Y-%m"))
    batch_id = request.args.get("batch_id")
    status = request.args.get("status")
    search = request.args.get("search")

    data = FeeService.get_monthly_fee_records(
        month_year=month_year,
        batch_id=batch_id,
        status=status,
        search=search
    )
    return jsonify({"success": True, "data": data})

@app.route("/api/fees/pending", methods=["GET"])
@login_required
def api_get_pending_fees():
    batch_id = request.args.get("batch_id")
    search = request.args.get("search")
    min_days = int(request.args.get("min_days", 0))

    defaulters = FeeService.get_pending_defaulters(
        batch_id=batch_id,
        search=search,
        min_days=min_days
    )
    return jsonify({"success": True, "data": defaulters})

# --- Payments API ---
@app.route("/api/payments", methods=["GET"])
@login_required
def api_get_payments():
    search = request.args.get("search")
    method = request.args.get("method")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    result = PaymentService.get_payments(
        search=search,
        method=method,
        start_date=start_date,
        end_date=end_date,
        page=page,
        per_page=per_page
    )
    return jsonify({"success": True, "data": result})

@app.route("/api/payments", methods=["POST"])
@login_required
def api_record_payment():
    data = request.get_json() or {}
    success, msg, receipt = PaymentService.record_payment(data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg, "data": receipt}), 201

@app.route("/api/payments/<payment_id>/receipt", methods=["GET"])
@login_required
def api_get_payment_receipt(payment_id):
    receipt = PaymentService.get_receipt_data(payment_id)
    if not receipt:
        return jsonify({"success": False, "error": "Receipt not found"}), 404
    return jsonify({"success": True, "data": receipt})

@app.route("/api/payments/<payment_id>/reverse", methods=["POST"])
@login_required
def api_reverse_payment(payment_id):
    data = request.get_json() or {}
    reason = data.get("reason", "")
    success, msg = PaymentService.reverse_payment(payment_id, reason)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg})

# --- Reports & Exports API ---
@app.route("/api/reports/collection", methods=["GET"])
@login_required
def api_report_collection():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    method = request.args.get("method")
    batch_id = request.args.get("batch_id")

    report = ReportService.get_collection_report(
        start_date=start_date,
        end_date=end_date,
        payment_method=method,
        batch_id=batch_id
    )
    return jsonify({"success": True, "data": report})

@app.route("/api/reports/batch-summary", methods=["GET"])
@login_required
def api_report_batch_summary():
    report = ReportService.get_batch_summary_report()
    return jsonify({"success": True, "data": report})

@app.route("/api/reports/admissions", methods=["GET"])
@login_required
def api_report_admissions():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    batch_id = request.args.get("batch_id")

    report = ReportService.get_admission_report(
        start_date=start_date,
        end_date=end_date,
        batch_id=batch_id
    )
    return jsonify({"success": True, "data": report})

@app.route("/api/reports/export/collection.csv")
@login_required
def export_collection_csv():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    method = request.args.get("method")
    batch_id = request.args.get("batch_id")

    report = ReportService.get_collection_report(
        start_date=start_date,
        end_date=end_date,
        payment_method=method,
        batch_id=batch_id
    )

    headers = ["Receipt No", "Payment Date", "Student ID", "Student Name", "Batch", "Payment Method", "Reference No", "Amount (INR)"]
    rows = [
        [
            p["receipt_no"],
            p["payment_date"],
            p["student_id"],
            p["student_name"],
            p["batch_name"],
            p["payment_method"],
            p["reference_no"],
            p["amount_rupees"]
        ]
        for p in report["payments"]
    ]

    csv_data = ReportService.generate_csv(headers, rows)
    filename = f"fee_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route("/api/reports/export/pending.csv")
@login_required
def export_pending_csv():
    batch_id = request.args.get("batch_id")
    search = request.args.get("search")
    defaulters = FeeService.get_pending_defaulters(batch_id=batch_id, search=search)

    headers = ["Student ID", "Student Name", "Phone", "Parent Name", "Parent Phone", "Batch", "Oldest Due Date", "Days Overdue", "Total Pending (INR)", "Status"]
    rows = [
        [
            d["student_id"],
            d["student_name"],
            d["phone"],
            d["parent_name"],
            d["parent_phone"],
            d["batch_name"],
            d["formatted_oldest_due_date"],
            d["days_overdue"],
            paise_to_rupees(d["total_pending_paise"]),
            d["status"]
        ]
        for d in defaulters
    ]

    csv_data = ReportService.generate_csv(headers, rows)
    filename = f"pending_fees_defaulters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

# --- Settings API ---
@app.route("/api/settings", methods=["POST"])
@login_required
def api_update_settings():
    data = request.get_json() or {}
    success, msg = SettingsService.update_settings(data)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg})

@app.route("/api/settings/password", methods=["POST"])
@login_required
def api_change_password():
    data = request.get_json() or {}
    old_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")
    username = session.get("username")

    success, msg = AuthService.change_password(username, old_pw, new_pw)
    if not success:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "message": msg})


if __name__ == "__main__":
    # Auto-seed sample demo data if students collection is empty
    try:
        from seed_demo_data import seed
        db = get_db()
        if db.students.count_documents({}) == 0:
            seed()
    except Exception as e:
        pass

    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    app.run(host="127.0.0.1", port=port, debug=debug)
