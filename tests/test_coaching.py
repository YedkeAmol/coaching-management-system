import pytest
import mongomock
from app import app
from database import (
    get_db_manager,
    set_db,
    rupees_to_paise,
    paise_to_rupees,
    format_inr,
    format_date_indian,
    parse_indian_date
)
from services.auth_service import AuthService
from services.student_service import StudentService
from services.batch_service import BatchService
from services.fee_service import FeeService
from services.payment_service import PaymentService
from services.report_service import ReportService
from services.settings_service import SettingsService

@pytest.fixture(autouse=True)
def isolated_db():
    """Sets up an isolated in-memory mongomock database for each test."""
    mock_client = mongomock.MongoClient()
    test_db = mock_client["test_coaching_db"]
    set_db(test_db)
    # Ensure fresh indexes & initial seed
    get_db_manager()._ensure_indexes()
    get_db_manager()._seed_initial_data()
    yield test_db

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client

# 1. Currency & Paise Conversion Accuracy
def test_rupees_and_paise_conversion():
    assert rupees_to_paise(1500) == 150000
    assert rupees_to_paise(1500.50) == 150050
    assert rupees_to_paise("1,25,000.00") == 12500000
    assert paise_to_rupees(150050) == 1500.50
    assert paise_to_rupees(0) == 0.0

# 2. Indian Numbering Currency Formatting (₹1,25,000.00)
def test_format_inr():
    assert format_inr(12500000) == "₹1,25,000.00"
    assert format_inr(150050) == "₹1,500.50"
    assert format_inr(0) == "₹0.00"
    assert format_inr(-50000) == "-₹500.00"

# 3. Date Formatting and Parsing
def test_date_utilities():
    assert format_date_indian("2026-10-30") == "30-10-2026"
    assert parse_indian_date("30-10-2026") == "2026-10-30"

# 4. Authentication Flow & Password Hashing
def test_auth_service():
    user = AuthService.authenticate("admin", "admin123")
    assert user is not None
    assert user["username"] == "admin"

    # Wrong credentials
    assert AuthService.authenticate("admin", "wrongpassword") is None
    assert AuthService.authenticate("nonexistent", "pass") is None

# 5. Course & Batch Creation
def test_batch_and_course_creation():
    ok, msg, course = BatchService.create_course({
        "course_name": "Class 10 Science",
        "default_fee": 1600.0
    })
    assert ok is True
    assert course["course_name"] == "Class 10 Science"

    ok, msg, batch = BatchService.create_batch({
        "batch_name": "Science Morning",
        "course_id": course["course_id"],
        "default_monthly_fee": 1600.0
    })
    assert ok is True
    assert batch["batch_name"] == "Science Morning"
    assert batch["student_count"] == 0

# 6. Student Admission & Auto-generated Fee Dues
def test_student_creation_and_dues():
    ok, msg, student = StudentService.create_student({
        "full_name": "Test Student",
        "phone": "9876543211",
        "batch_id": "BAT-01",
        "monthly_fee": 1000.0,
        "admission_date": "2026-10-01"
    })
    assert ok is True
    assert student["student_id"].startswith("STU-")
    assert student["full_name"] == "Test Student"

    # Verify student fee summary
    summary = FeeService.get_student_fee_summary(student["student_id"])
    assert summary is not None
    assert summary["total_billed_rupees"] >= 1000.0
    assert summary["total_paid_rupees"] == 0.0

# 7. Exact Ledger Scenario:
# (October ₹1,000 due, ₹600 paid, ₹400 balance -> ₹400 paid, ₹0 balance)
def test_prompt_fee_ledger_scenario(isolated_db):
    ok, _, student = StudentService.create_student({
        "full_name": "Ravi Kumar",
        "phone": "9876543299",
        "batch_id": "BAT-01",
        "monthly_fee": 1000.0,
        "admission_date": "2026-10-01"
    })
    sid = student["student_id"]

    # Partial Payment 1: ₹600
    ok, msg, p1 = PaymentService.record_payment({
        "student_id": sid,
        "amount": 600.0,
        "payment_method": "Cash"
    })
    assert ok is True

    summary1 = FeeService.get_student_fee_summary(sid)
    assert summary1["total_paid_rupees"] == 600.0
    assert summary1["total_pending_rupees"] == 400.0

    # Payment 2: ₹400 (Settle remaining balance)
    ok, msg, p2 = PaymentService.record_payment({
        "student_id": sid,
        "amount": 400.0,
        "payment_method": "UPI",
        "reference_no": "UPI-SETTLE-400"
    })
    assert ok is True

    summary2 = FeeService.get_student_fee_summary(sid)
    assert summary2["total_paid_rupees"] == 1000.0
    assert summary2["total_pending_rupees"] == 0.0

# 8. Advance Payment and Automatic Credit Consumption
def test_advance_payment_and_credit():
    ok, _, student = StudentService.create_student({
        "full_name": "Pooja Sharma",
        "phone": "9876543288",
        "batch_id": "BAT-01",
        "monthly_fee": 1000.0,
        "admission_date": "2026-10-01"
    })
    sid = student["student_id"]

    # Student pays ₹2500 (covers 1000 due, +1500 excess advance)
    ok, msg, p = PaymentService.record_payment({
        "student_id": sid,
        "amount": 2500.0,
        "payment_method": "Bank Transfer"
    })
    assert ok is True
    assert p["excess_advance_rupees"] == 1500.0

    summary = FeeService.get_student_fee_summary(sid)
    assert summary["advance_balance_rupees"] == 1500.0
    assert summary["total_pending_rupees"] == 0.0

# 9. Prevention of Duplicate Payment Submissions
def test_duplicate_payment_prevention():
    ok, _, student = StudentService.create_student({
        "full_name": "Amit Patel",
        "phone": "9876543277",
        "batch_id": "BAT-01",
        "monthly_fee": 1000.0
    })
    sid = student["student_id"]

    ok1, _, _ = PaymentService.record_payment({
        "student_id": sid,
        "amount": 1000.0,
        "reference_no": "DUP-REF-1234"
    })
    assert ok1 is True

    # Same reference submitted again
    ok2, err, _ = PaymentService.record_payment({
        "student_id": sid,
        "amount": 1000.0,
        "reference_no": "DUP-REF-1234"
    })
    assert ok2 is False
    assert "already exists" in err

# 10. Controlled Payment Reversal Maintaining Full Audit Trail
def test_payment_reversal():
    ok, _, student = StudentService.create_student({
        "full_name": "Neha Gupta",
        "phone": "9876543266",
        "batch_id": "BAT-01",
        "monthly_fee": 1500.0
    })
    sid = student["student_id"]

    ok, _, pay = PaymentService.record_payment({
        "student_id": sid,
        "amount": 1500.0,
        "payment_method": "Cheque",
        "reference_no": "CHQ-8899"
    })
    receipt_no = pay["receipt_no"]

    # Reversal requires mandatory reason
    ok_fail, msg = PaymentService.reverse_payment(receipt_no, reason="")
    assert ok_fail is False

    # Reverse with reason
    ok_rev, msg = PaymentService.reverse_payment(receipt_no, reason="Cheque bounced due to signature mismatch")
    assert ok_rev is True

    # Dues must be restored
    summary = FeeService.get_student_fee_summary(sid)
    assert summary["total_paid_rupees"] == 0.0
    assert summary["total_pending_rupees"] == 1500.0

    # Receipt still exists with reversed flag
    rcpt = PaymentService.get_receipt_data(receipt_no)
    assert rcpt["is_reversed"] is True
    assert "signature mismatch" in rcpt["reversal_reason"]

# 11. Safe Archiving on Student Deletion with History
def test_safe_archiving_of_students():
    ok, _, student = StudentService.create_student({
        "full_name": "Vikas Singh",
        "phone": "9876543255",
        "batch_id": "BAT-01",
        "monthly_fee": 1000.0
    })
    sid = student["student_id"]

    PaymentService.record_payment({
        "student_id": sid,
        "amount": 1000.0
    })

    # Attempt to delete student with payments
    ok, msg = StudentService.delete_or_archive_student(sid)
    assert ok is True
    assert "archived" in msg.lower()

    # Student still exists as Archived
    s = StudentService.get_student_by_id(sid)
    assert s is not None
    assert s["status"] == "Archived"

# 12. Input Validation (Negative Amounts & Invalid Phones)
def test_validation_rules():
    # Negative amount
    ok, err, _ = PaymentService.record_payment({
        "student_id": "STU-FAKE",
        "amount": -500
    })
    assert ok is False

    # Zero amount
    ok, err, _ = PaymentService.record_payment({
        "student_id": "STU-FAKE",
        "amount": 0
    })
    assert ok is False

    # Excessive amount (> ₹10 Lakh)
    ok, err, _ = PaymentService.record_payment({
        "student_id": "STU-FAKE",
        "amount": 15000000
    })
    assert ok is False

    # Invalid phone (too short)
    ok, err, _ = StudentService.create_student({
        "full_name": "Invalid Student",
        "phone": "123"
    })
    assert ok is False

    # Invalid phone (doesn't start with 6-9)
    ok, err, _ = StudentService.create_student({
        "full_name": "Invalid Student",
        "phone": "2234567890"
    })
    assert ok is False

    # Invalid name (empty or symbols only)
    ok, err, _ = StudentService.create_student({
        "full_name": "   ",
        "phone": "9876543210"
    })
    assert ok is False

    # Reversal reason too short (< 5 chars)
    ok_rev, msg = PaymentService.reverse_payment("REC-202610-9999", reason="bad")
    assert ok_rev is False
    assert "minimum 5 characters" in msg

    # Password cannot be identical to old password
    ok_pw, msg_pw = AuthService.change_password("admin", "admin123", "admin123")
    assert ok_pw is False
    assert "different" in msg_pw

    # Duplicate active phone enrollment
    ok1, _, s1 = StudentService.create_student({
        "full_name": "First Student",
        "phone": "9811122233",
        "batch_id": "BAT-01"
    })
    assert ok1 is True
    ok2, err2, _ = StudentService.create_student({
        "full_name": "Second Student",
        "phone": "9811122233",
        "batch_id": "BAT-01"
    })
    assert ok2 is False
    assert "already actively enrolled" in err2

# 13. Route Security & Authentication Check
def test_protected_routes(client):
    # Unauthenticated access to dashboard should redirect to login
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]

    # Unauthenticated API access should return 401
    res_api = client.get("/api/dashboard")
    assert res_api.status_code == 401
