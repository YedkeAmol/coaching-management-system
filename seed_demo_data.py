"""
Seed Script to populate sample students, fees, and payments
for realistic demonstration of the Coaching Management System.
"""
from datetime import datetime, timezone
from database import get_db, rupees_to_paise
from services.student_service import StudentService
from services.payment_service import PaymentService
from services.fee_service import FeeService

def seed():
    db = get_db()
    print("Seeding sample students and initial financial records...")

    sample_students = [
        {
            "student_id": "STU-2026-0001",
            "full_name": "Aarav Sharma",
            "phone": "9876543201",
            "parent_name": "Rajesh Sharma",
            "parent_phone": "9876543202",
            "address": "B-42, Mayur Vihar, New Delhi",
            "batch_id": "BAT-01",
            "admission_date": "2026-08-01",
            "monthly_fee": 1500.0,
            "fee_due_day": 5,
            "notes": "Targeting 95%+ in Board Exam"
        },
        {
            "student_id": "STU-2026-0002",
            "full_name": "Diya Patel",
            "phone": "9876543203",
            "parent_name": "Kirit Patel",
            "parent_phone": "9876543204",
            "address": "Flat 302, Green Park, New Delhi",
            "batch_id": "BAT-02",
            "admission_date": "2026-08-15",
            "monthly_fee": 2000.0,
            "fee_due_day": 5,
            "notes": "JEE Main preparation"
        },
        {
            "student_id": "STU-2026-0003",
            "full_name": "Kabir Verma",
            "phone": "9876543205",
            "parent_name": "Alok Verma",
            "parent_phone": "9876543206",
            "address": "C-12, Sector 15, Noida",
            "batch_id": "BAT-01",
            "admission_date": "2026-09-01",
            "monthly_fee": 1500.0,
            "fee_due_day": 5,
            "notes": "Needs extra practice in Quadratic Equations"
        },
        {
            "student_id": "STU-2026-0004",
            "full_name": "Ananya Joshi",
            "phone": "9876543207",
            "parent_name": "Vikram Joshi",
            "parent_phone": "9876543208",
            "address": "House 88, Vasant Kunj, New Delhi",
            "batch_id": "BAT-03",
            "admission_date": "2026-09-10",
            "monthly_fee": 1800.0,
            "fee_due_day": 5,
            "notes": "NEET Chemistry Aspirant"
        },
        {
            "student_id": "STU-2026-0005",
            "full_name": "Rohan Gupta",
            "phone": "9876543209",
            "parent_name": "Sanjay Gupta",
            "parent_phone": "9876543210",
            "address": "D-5, Rohini Sector 9, Delhi",
            "batch_id": "BAT-02",
            "admission_date": "2026-10-01",
            "monthly_fee": 2000.0,
            "fee_due_day": 5,
            "notes": "New enrollment for Class 12 batch"
        }
    ]

    for s in sample_students:
        existing = db.students.find_one({"student_id": s["student_id"]})
        if not existing:
            ok, msg, created = StudentService.create_student(s)
            print(f"Created student {s['full_name']} ({s['student_id']}): {ok}")
        else:
            print(f"Student {s['student_id']} already exists.")

    # Record realistic sample payments
    # Student 1: Paid for August and September, partial payment for October
    if db.payments.count_documents({"student_id": "STU-2026-0001"}) == 0:
        PaymentService.record_payment({
            "student_id": "STU-2026-0001",
            "amount": 3000.0, # Covers Aug & Sep (1500 + 1500)
            "payment_date": "2026-08-05",
            "payment_method": "UPI",
            "reference_no": "UPI-AUG-3000-01",
            "notes": "Paid by Father for Aug & Sep"
        })
        PaymentService.record_payment({
            "student_id": "STU-2026-0001",
            "amount": 1000.0, # Partial payment of October (500 remaining)
            "payment_date": "2026-10-06",
            "payment_method": "Cash",
            "notes": "Partial fees for October"
        })

    # Student 2: Paid in advance covering October and November!
    if db.payments.count_documents({"student_id": "STU-2026-0002"}) == 0:
        PaymentService.record_payment({
            "student_id": "STU-2026-0002",
            "amount": 6000.0, # Aug, Sep, Oct (2000 x 3 = 6000)
            "payment_date": "2026-08-16",
            "payment_method": "Bank Transfer",
            "reference_no": "NEFT-HDFC-992384"
        })
        PaymentService.record_payment({
            "student_id": "STU-2026-0002",
            "amount": 4000.0, # Nov & Dec advance!
            "payment_date": "2026-10-02",
            "payment_method": "UPI",
            "reference_no": "UPI-ADV-4000"
        })

    # Student 3: Has unpaid September and October dues (Defaulter)
    # (No payments recorded -> will show as overdue in defaulters report!)

    # Student 4: Paid September, October pending
    if db.payments.count_documents({"student_id": "STU-2026-0004"}) == 0:
        PaymentService.record_payment({
            "student_id": "STU-2026-0004",
            "amount": 1800.0,
            "payment_date": "2026-09-12",
            "payment_method": "Cash"
        })

    print("Sample data successfully seeded!")

if __name__ == "__main__":
    seed()
