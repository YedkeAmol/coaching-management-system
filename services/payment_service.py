from datetime import datetime, timezone, timedelta
from bson import ObjectId
import re
from database import (
    get_db,
    rupees_to_paise,
    paise_to_rupees,
    format_inr,
    format_date_indian,
    parse_indian_date
)
from services.validation_service import ValidationService

class PaymentService:
    @staticmethod
    def get_payments(search=None, method=None, start_date=None, end_date=None, page=1, per_page=20):
        db = get_db()
        query = {}

        if method and method.lower() != "all":
            query["payment_method"] = method

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = parse_indian_date(start_date)
            if end_date:
                date_filter["$lte"] = parse_indian_date(end_date)
            query["payment_date"] = date_filter

        if search:
            search_regex = {"$regex": re.escape(search.strip()), "$options": "i"}
            query["$or"] = [
                {"receipt_no": search_regex},
                {"student_id": search_regex},
                {"student_name": search_regex},
                {"reference_no": search_regex}
            ]

        total = db.payments.count_documents(query)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages)) if total > 0 else 1
        skip = (page - 1) * per_page

        cursor = db.payments.find(query).sort("payment_date", -1).skip(skip).limit(per_page)
        payments = list(cursor)

        for p in payments:
            p["_id"] = str(p.get("_id"))
            p["amount_rupees"] = paise_to_rupees(p.get("amount_paise", 0))
            p["formatted_amount"] = format_inr(p.get("amount_paise", 0))
            p["formatted_payment_date"] = format_date_indian(p.get("payment_date", ""))

        return {
            "payments": payments,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }

    @staticmethod
    def record_payment(data):
        if not data:
            return False, "Payment data is required.", None

        student_id = str(data.get("student_id", "")).strip()
        if not student_id:
            return False, "Student ID is required.", None

        db = get_db()
        student = db.students.find_one({"student_id": student_id})
        if not student:
            return False, f"Student '{student_id}' not found.", None

        raw_amount = data.get("amount") or data.get("amount_rupees") or 0
        ok_amt, msg_amt = ValidationService.validate_amount(raw_amount, "Payment amount", min_val=1.0, max_val=1000000.0)
        if not ok_amt:
            return False, msg_amt, None
        amount_paise = rupees_to_paise(raw_amount)

        payment_method = str(data.get("payment_method", "Cash")).strip() or "Cash"
        reference_no = str(data.get("reference_no", "")).strip()

        # Duplicate payment check by reference number
        if reference_no:
            dup = db.payments.find_one({
                "student_id": student_id,
                "reference_no": reference_no,
                "is_reversed": {"$ne": True}
            })
            if dup:
                return False, f"Payment with reference '{reference_no}' already exists.", None

        # Rapid duplicate payment debounce (prevents accidental double submission within 5 seconds)
        ten_sec_ago = datetime.now(timezone.utc) - timedelta(seconds=5)
        recent_dup = db.payments.find_one({
            "student_id": student_id,
            "amount_paise": amount_paise,
            "created_at": {"$gte": ten_sec_ago},
            "is_reversed": {"$ne": True}
        })
        if recent_dup:
            return False, "A payment for the exact same amount was just submitted. Please wait a few seconds to avoid duplicates.", None

        payment_date = parse_indian_date(str(data.get("payment_date", "")).strip())
        if not payment_date:
            payment_date = datetime.now().strftime("%Y-%m-%d")

        # Generate Receipt Number: REC-YYYYMM-XXXX
        ym_prefix = datetime.now().strftime("%Y%m")
        prefix = f"REC-{ym_prefix}-"
        count = db.payments.count_documents({"receipt_no": {"$regex": f"^{prefix}"}}) + 1
        receipt_no = f"{prefix}{count:04d}"
        while db.payments.find_one({"receipt_no": receipt_no}):
            count += 1
            receipt_no = f"{prefix}{count:04d}"

        batch = db.batches.find_one({"batch_id": student.get("batch_id")})
        batch_name = batch.get("batch_name", "Unassigned") if batch else "Unassigned"

        payment_doc = {
            "receipt_no": receipt_no,
            "student_id": student_id,
            "student_name": student.get("full_name"),
            "batch_id": student.get("batch_id"),
            "batch_name": batch_name,
            "amount_paise": amount_paise,
            "amount_rupees": paise_to_rupees(amount_paise),
            "payment_date": payment_date,
            "payment_method": payment_method,
            "reference_no": reference_no,
            "notes": str(data.get("notes", "")).strip(),
            "is_reversed": False,
            "created_at": datetime.now(timezone.utc)
        }
        res = db.payments.insert_one(payment_doc)
        payment_id = str(res.inserted_id)
        payment_doc["_id"] = payment_id

        # Chronological Ledger Allocation:
        # Settle oldest unpaid dues first
        remaining_paise = amount_paise
        unpaid_dues = list(db.fee_dues.find({
            "student_id": student_id,
            "status": {"$in": ["Pending", "Partially Paid", "Overdue"]}
        }).sort("month_year", 1))

        allocations = []
        for due in unpaid_dues:
            if remaining_paise <= 0:
                break

            due_balance = due.get("balance_paise", 0)
            allocated = min(remaining_paise, due_balance)
            new_paid = due.get("paid_amount_paise", 0) + allocated
            new_balance = due_balance - allocated
            new_status = "Paid" if new_balance == 0 else "Partially Paid"

            db.fee_dues.update_one(
                {"_id": due["_id"]},
                {"$set": {
                    "paid_amount_paise": new_paid,
                    "balance_paise": new_balance,
                    "status": new_status,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

            alloc_doc = {
                "payment_id": payment_id,
                "receipt_no": receipt_no,
                "fee_due_id": str(due["_id"]),
                "student_id": student_id,
                "month_year": due.get("month_year"),
                "allocated_amount_paise": allocated,
                "created_at": datetime.now(timezone.utc)
            }
            db.payment_allocations.insert_one(alloc_doc)
            alloc_doc["allocated_amount_rupees"] = paise_to_rupees(allocated)
            allocations.append(alloc_doc)

            remaining_paise -= allocated

        # Any unallocated excess amount is carried forward as Advance Credit
        if remaining_paise > 0:
            db.students.update_one(
                {"student_id": student_id},
                {"$inc": {"advance_balance_paise": remaining_paise}}
            )

        payment_doc["allocations"] = allocations
        payment_doc["excess_advance_paise"] = remaining_paise
        payment_doc["excess_advance_rupees"] = paise_to_rupees(remaining_paise)
        return True, f"Payment of {format_inr(amount_paise)} recorded. Receipt #{receipt_no}", payment_doc

    @staticmethod
    def get_receipt_data(payment_id_or_receipt_no):
        db = get_db()
        query = {"receipt_no": payment_id_or_receipt_no}
        try:
            if ObjectId.is_valid(payment_id_or_receipt_no):
                query = {"$or": [{"receipt_no": payment_id_or_receipt_no}, {"_id": ObjectId(payment_id_or_receipt_no)}]}
        except Exception:
            pass

        payment = db.payments.find_one(query)
        if not payment:
            return None

        payment["_id"] = str(payment.get("_id"))
        payment["formatted_amount"] = format_inr(payment.get("amount_paise", 0))
        payment["formatted_payment_date"] = format_date_indian(payment.get("payment_date", ""))

        student = db.students.find_one({"student_id": payment.get("student_id")}) or {}
        settings = db.settings.find_one({"_id": "global"}) or {}

        # Allocations
        allocations = list(db.payment_allocations.find({
            "$or": [
                {"payment_id": str(payment["_id"])},
                {"receipt_no": payment["receipt_no"]}
            ]
        }))

        for a in allocations:
            a["_id"] = str(a.get("_id"))
            a["formatted_allocated"] = format_inr(a.get("allocated_amount_paise", 0))
            a["allocated_rupees"] = paise_to_rupees(a.get("allocated_amount_paise", 0))

        # Overall student pending balance after payment
        pending_dues = list(db.fee_dues.find({
            "student_id": payment.get("student_id"),
            "status": {"$in": ["Pending", "Partially Paid", "Overdue"]}
        }))
        remaining_balance_paise = sum(d.get("balance_paise", 0) for d in pending_dues)

        return {
            "receipt_no": payment["receipt_no"],
            "payment_id": str(payment["_id"]),
            "payment_date": payment["payment_date"],
            "formatted_payment_date": payment["formatted_payment_date"],
            "payment_method": payment.get("payment_method"),
            "reference_no": payment.get("reference_no", "N/A"),
            "amount_paise": payment.get("amount_paise", 0),
            "amount_rupees": payment.get("amount_rupees", 0.0),
            "formatted_amount": payment["formatted_amount"],
            "notes": payment.get("notes", ""),
            "is_reversed": payment.get("is_reversed", False),
            "reversal_reason": payment.get("reversal_reason", ""),
            "reversal_date": format_date_indian(payment.get("reversal_date", "")),
            "student": {
                "student_id": student.get("student_id"),
                "full_name": student.get("full_name"),
                "phone": student.get("phone"),
                "parent_name": student.get("parent_name"),
                "parent_phone": student.get("parent_phone"),
                "address": student.get("address"),
                "batch_name": payment.get("batch_name", "General"),
                "remaining_balance_rupees": paise_to_rupees(remaining_balance_paise),
                "formatted_remaining_balance": format_inr(remaining_balance_paise),
                "advance_balance_rupees": paise_to_rupees(student.get("advance_balance_paise", 0)),
                "formatted_advance_balance": format_inr(student.get("advance_balance_paise", 0))
            },
            "institute": {
                "name": settings.get("institute_name", "Apex Coaching Academy"),
                "address": settings.get("address", ""),
                "contact": settings.get("contact_number", ""),
                "email": settings.get("email", "")
            },
            "allocations": allocations
        }

    @staticmethod
    def reverse_payment(payment_id, reason=""):
        if not payment_id:
            return False, "Payment ID is required."
        
        if not reason or len(str(reason).strip()) < 5:
            return False, "A clear reason (minimum 5 characters) is mandatory for reversing a financial transaction."
        
        db = get_db()
        query = {"receipt_no": payment_id}
        try:
            if ObjectId.is_valid(payment_id):
                query = {"$or": [{"receipt_no": payment_id}, {"_id": ObjectId(payment_id)}]}
        except Exception:
            pass

        payment = db.payments.find_one(query)
        if not payment:
            return False, "Payment record not found."

        if payment.get("is_reversed"):
            return False, "This payment transaction has already been reversed."

        today_str = datetime.now().strftime("%Y-%m-%d")
        pay_id_str = str(payment["_id"])
        receipt_no = payment["receipt_no"]
        student_id = payment["student_id"]

        # Step 1: Revert all allocations made by this payment
        allocations = list(db.payment_allocations.find({
            "$or": [{"payment_id": pay_id_str}, {"receipt_no": receipt_no}]
        }))

        total_allocated = 0
        for alloc in allocations:
            fee_due_id = alloc.get("fee_due_id")
            allocated_amount = alloc.get("allocated_amount_paise", 0)
            total_allocated += allocated_amount

            # Fetch and revert the fee due
            due = None
            try:
                if ObjectId.is_valid(fee_due_id):
                    due = db.fee_dues.find_one({"_id": ObjectId(fee_due_id)})
            except Exception:
                pass
            if not due:
                due = db.fee_dues.find_one({"student_id": student_id, "month_year": alloc.get("month_year")})

            if due:
                new_paid = max(0, due.get("paid_amount_paise", 0) - allocated_amount)
                new_balance = due.get("amount_due_paise", 0) - new_paid
                new_status = "Paid" if new_balance == 0 else ("Partially Paid" if new_paid > 0 else ("Overdue" if due.get("due_date", "") < today_str else "Pending"))
                db.fee_dues.update_one(
                    {"_id": due["_id"]},
                    {"$set": {
                        "paid_amount_paise": new_paid,
                        "balance_paise": new_balance,
                        "status": new_status,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )

        # Step 2: If there was unallocated amount that increased advance balance, deduct it
        excess_paise = max(0, payment.get("amount_paise", 0) - total_allocated)
        if excess_paise > 0:
            db.students.update_one(
                {"student_id": student_id},
                {"$inc": {"advance_balance_paise": -excess_paise}}
            )

        # Step 3: Delete allocations & mark payment as reversed (Preserve audit trail)
        db.payment_allocations.delete_many({
            "$or": [{"payment_id": pay_id_str}, {"receipt_no": receipt_no}]
        })

        db.payments.update_one(
            {"_id": payment["_id"]},
            {"$set": {
                "is_reversed": True,
                "reversal_reason": reason.strip(),
                "reversal_date": today_str,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        return True, f"Receipt #{receipt_no} reversed successfully. Dues and ledger restored."
