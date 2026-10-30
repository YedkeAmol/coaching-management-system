from datetime import datetime, timezone
import re
from database import (
    get_db,
    rupees_to_paise,
    paise_to_rupees,
    format_inr,
    format_date_indian
)

class FeeService:
    @staticmethod
    def get_student_fee_summary(student_id):
        if not student_id:
            return None
        
        db = get_db()
        student = db.students.find_one({"student_id": student_id})
        if not student:
            return None

        today_str = datetime.now().strftime("%Y-%m-%d")

        # Update any pending dues to overdue if due_date has passed
        db.fee_dues.update_many(
            {
                "student_id": student_id,
                "status": "Pending",
                "due_date": {"$lt": today_str},
                "balance_paise": {"$gt": 0}
            },
            {"$set": {"status": "Overdue"}}
        )

        dues = list(db.fee_dues.find({"student_id": student_id}).sort("month_year", 1))
        payments = list(db.payments.find({"student_id": student_id}).sort("payment_date", -1))

        total_billed_paise = sum(d.get("amount_due_paise", 0) for d in dues)
        total_paid_paise = sum(d.get("paid_amount_paise", 0) for d in dues)
        total_pending_paise = sum(d.get("balance_paise", 0) for d in dues if d.get("status") in ["Pending", "Partially Paid", "Overdue"])
        advance_balance_paise = student.get("advance_balance_paise", 0)

        # Format dues for UI
        for d in dues:
            d["_id"] = str(d.get("_id"))
            d["amount_due_rupees"] = paise_to_rupees(d.get("amount_due_paise", 0))
            d["paid_amount_rupees"] = paise_to_rupees(d.get("paid_amount_paise", 0))
            d["balance_rupees"] = paise_to_rupees(d.get("balance_paise", 0))
            d["formatted_due_date"] = format_date_indian(d.get("due_date", ""))

        for p in payments:
            p["_id"] = str(p.get("_id"))
            p["amount_rupees"] = paise_to_rupees(p.get("amount_paise", 0))
            p["formatted_payment_date"] = format_date_indian(p.get("payment_date", ""))

        return {
            "student_id": student_id,
            "student_name": student.get("full_name"),
            "advance_balance_paise": advance_balance_paise,
            "advance_balance_rupees": paise_to_rupees(advance_balance_paise),
            "formatted_advance_balance": format_inr(advance_balance_paise),
            "total_billed_paise": total_billed_paise,
            "total_billed_rupees": paise_to_rupees(total_billed_paise),
            "formatted_total_billed": format_inr(total_billed_paise),
            "total_paid_paise": total_paid_paise,
            "total_paid_rupees": paise_to_rupees(total_paid_paise),
            "formatted_total_paid": format_inr(total_paid_paise),
            "total_pending_paise": total_pending_paise,
            "total_pending_rupees": paise_to_rupees(total_pending_paise),
            "formatted_total_pending": format_inr(total_pending_paise),
            "dues": dues,
            "payments": payments
        }

    @staticmethod
    def get_monthly_fee_records(month_year, batch_id=None, status=None, search=None):
        db = get_db()
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Auto-create fee dues for any active student for this month if missing
        active_students = list(db.students.find({"status": "Active"}))
        batches_map = {b["batch_id"]: b["batch_name"] for b in db.batches.find({})}

        for s in active_students:
            adm_my = s.get("admission_date", "2020-01")[:7]
            if adm_my <= month_year:
                existing = db.fee_dues.find_one({"student_id": s["student_id"], "month_year": month_year})
                if not existing:
                    fee_paise = s.get("monthly_fee_paise", 150000)
                    due_day = s.get("fee_due_day", 5)
                    due_date = f"{month_year}-{due_day:02d}"
                    st = "Overdue" if due_date < today_str else "Pending"
                    db.fee_dues.insert_one({
                        "student_id": s["student_id"],
                        "month_year": month_year,
                        "amount_due_paise": fee_paise,
                        "paid_amount_paise": 0,
                        "balance_paise": fee_paise,
                        "due_date": due_date,
                        "status": st,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    })

        # Update overdue statuses
        db.fee_dues.update_many(
            {
                "month_year": month_year,
                "status": "Pending",
                "due_date": {"$lt": today_str},
                "balance_paise": {"$gt": 0}
            },
            {"$set": {"status": "Overdue"}}
        )

        query = {"month_year": month_year}
        if status and status.lower() != "all":
            query["status"] = status

        dues = list(db.fee_dues.find(query))
        records = []

        students_map = {s["student_id"]: s for s in db.students.find({})}

        for d in dues:
            s = students_map.get(d["student_id"])
            if not s:
                continue

            if batch_id and batch_id.lower() != "all" and s.get("batch_id") != batch_id:
                continue

            if search:
                pattern = re.escape(search.strip())
                matched = (
                    re.search(pattern, s.get("full_name", ""), re.IGNORECASE) or
                    re.search(pattern, s.get("student_id", ""), re.IGNORECASE) or
                    re.search(pattern, s.get("phone", ""), re.IGNORECASE)
                )
                if not matched:
                    continue

            record = {
                "due_id": str(d.get("_id")),
                "student_id": s["student_id"],
                "student_name": s.get("full_name"),
                "phone": s.get("phone"),
                "batch_id": s.get("batch_id"),
                "batch_name": batches_map.get(s.get("batch_id"), "Unassigned"),
                "month_year": month_year,
                "due_date": d.get("due_date"),
                "formatted_due_date": format_date_indian(d.get("due_date")),
                "amount_due_paise": d.get("amount_due_paise", 0),
                "amount_due_rupees": paise_to_rupees(d.get("amount_due_paise", 0)),
                "paid_amount_paise": d.get("paid_amount_paise", 0),
                "paid_amount_rupees": paise_to_rupees(d.get("paid_amount_paise", 0)),
                "balance_paise": d.get("balance_paise", 0),
                "balance_rupees": paise_to_rupees(d.get("balance_paise", 0)),
                "status": d.get("status", "Pending")
            }
            records.append(record)

        records.sort(key=lambda x: x["student_name"])
        return records

    @staticmethod
    def get_pending_defaulters(batch_id=None, search=None, min_days=0):
        db = get_db()
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        # Find all overdue or pending dues with positive balance
        query = {
            "balance_paise": {"$gt": 0},
            "due_date": {"$lt": today_str}
        }
        overdue_dues = list(db.fee_dues.find(query).sort("due_date", 1))

        students_map = {s["student_id"]: s for s in db.students.find({})}
        batches_map = {b["batch_id"]: b["batch_name"] for b in db.batches.find({})}

        # Group by student_id
        student_dues = {}
        for d in overdue_dues:
            sid = d["student_id"]
            if sid not in student_dues:
                student_dues[sid] = []
            student_dues[sid].append(d)

        defaulters = []
        for sid, dues in student_dues.items():
            s = students_map.get(sid)
            if not s or s.get("status") == "Archived":
                continue

            if batch_id and batch_id.lower() != "all" and s.get("batch_id") != batch_id:
                continue

            if search:
                pattern = re.escape(search.strip())
                matched = (
                    re.search(pattern, s.get("full_name", ""), re.IGNORECASE) or
                    re.search(pattern, sid, re.IGNORECASE) or
                    re.search(pattern, s.get("phone", ""), re.IGNORECASE) or
                    re.search(pattern, s.get("parent_phone", ""), re.IGNORECASE)
                )
                if not matched:
                    continue

            oldest_due = dues[0]
            oldest_date_str = oldest_due.get("due_date", "")
            try:
                oldest_dt = datetime.strptime(oldest_date_str, "%Y-%m-%d")
                days_overdue = max(0, (today - oldest_dt).days)
            except Exception:
                days_overdue = 0

            if days_overdue < min_days:
                continue

            total_pending = sum(d.get("balance_paise", 0) for d in dues)

            status_label = "Severe Defaulter" if days_overdue > 60 else ("Overdue" if days_overdue > 30 else "Pending Due")

            defaulters.append({
                "student_id": sid,
                "student_name": s.get("full_name"),
                "phone": s.get("phone"),
                "parent_name": s.get("parent_name", "N/A"),
                "parent_phone": s.get("parent_phone", "N/A"),
                "batch_id": s.get("batch_id"),
                "batch_name": batches_map.get(s.get("batch_id"), "Unassigned"),
                "oldest_due_date": oldest_date_str,
                "formatted_oldest_due_date": format_date_indian(oldest_date_str),
                "days_overdue": days_overdue,
                "total_pending_paise": total_pending,
                "total_pending_rupees": paise_to_rupees(total_pending),
                "formatted_total_pending": format_inr(total_pending),
                "status": status_label,
                "unpaid_months_count": len(dues)
            })

        defaulters.sort(key=lambda x: x["days_overdue"], reverse=True)
        return defaulters
