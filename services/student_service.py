import re
from datetime import datetime, timezone
from database import (
    get_db,
    rupees_to_paise,
    paise_to_rupees,
    format_inr,
    format_date_indian,
    parse_indian_date
)
from services.validation_service import ValidationService

class StudentService:
    @staticmethod
    def get_students(search="", batch_id="", status="Active", page=1, per_page=20, sort_by="student_id", sort_order=1):
        db = get_db()
        query = {}
        
        if status and status.lower() != "all":
            query["status"] = status
            
        if batch_id and batch_id.lower() != "all":
            query["batch_id"] = batch_id
            
        if search:
            search_regex = {"$regex": re.escape(search.strip()), "$options": "i"}
            query["$or"] = [
                {"full_name": search_regex},
                {"student_id": search_regex},
                {"phone": search_regex},
                {"parent_phone": search_regex}
            ]

        total = db.students.count_documents(query)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages)) if total > 0 else 1
        skip = (page - 1) * per_page

        cursor = db.students.find(query).sort(sort_by, sort_order).skip(skip).limit(per_page)
        students = list(cursor)

        batches = {b["batch_id"]: b["batch_name"] for b in db.batches.find({})}

        for s in students:
            s["_id"] = str(s.get("_id"))
            s["batch_name"] = batches.get(s.get("batch_id"), s.get("batch_id", "Unassigned"))
            s["monthly_fee_rupees"] = paise_to_rupees(s.get("monthly_fee_paise", 0))
            s["advance_balance_rupees"] = paise_to_rupees(s.get("advance_balance_paise", 0))
            s["formatted_admission_date"] = format_date_indian(s.get("admission_date", ""))
            
            pending_dues = list(db.fee_dues.find({
                "student_id": s["student_id"],
                "status": {"$in": ["Pending", "Partially Paid", "Overdue"]}
            }))
            total_pending = sum(d.get("balance_paise", 0) for d in pending_dues)
            s["total_pending_paise"] = total_pending
            s["total_pending_rupees"] = paise_to_rupees(total_pending)
            s["formatted_pending_fee"] = format_inr(total_pending)

        return {
            "students": students,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }

    @staticmethod
    def create_student(data):
        if not data:
            return False, "Student data is required.", None
        
        full_name = str(data.get("full_name", "")).strip()
        ok_name, msg_name = ValidationService.validate_name(full_name, "Student full name")
        if not ok_name:
            return False, msg_name, None

        ok_phone, msg_phone, clean_phone = ValidationService.validate_indian_phone(data.get("phone"), "Student phone", required=True)
        if not ok_phone:
            return False, msg_phone, None

        parent_phone = str(data.get("parent_phone", "")).strip()
        clean_parent_phone = ""
        if parent_phone:
            ok_pp, msg_pp, clean_parent_phone = ValidationService.validate_indian_phone(parent_phone, "Parent phone", required=False)
            if not ok_pp:
                return False, msg_pp, None

        db = get_db()

        # Prevent duplicate active enrollment with identical phone
        existing_phone = db.students.find_one({"phone": clean_phone, "status": "Active"})
        if existing_phone:
            return False, f"A student with phone '{clean_phone}' is already actively enrolled ({existing_phone['full_name']} - {existing_phone['student_id']}).", None

        # Generate student ID: STU-YYYY-XXXX
        student_id = data.get("student_id")
        current_year = datetime.now().year
        if not student_id:
            prefix = f"STU-{current_year}-"
            count = db.students.count_documents({"student_id": {"$regex": f"^{prefix}"}}) + 1
            student_id = f"{prefix}{count:04d}"
            while db.students.find_one({"student_id": student_id}):
                count += 1
                student_id = f"{prefix}{count:04d}"
        else:
            student_id = str(student_id).strip()
            if db.students.find_one({"student_id": student_id}):
                return False, f"Student ID '{student_id}' already exists.", None

        batch_id = str(data.get("batch_id", "")).strip()
        # Resolve monthly fee
        monthly_fee_val = data.get("monthly_fee") or data.get("monthly_fee_rupees") or data.get("default_monthly_fee")
        if monthly_fee_val is not None and monthly_fee_val != "":
            ok_fee, msg_fee = ValidationService.validate_amount(monthly_fee_val, "Monthly fee", min_val=0.0, max_val=500000.0)
            if not ok_fee:
                return False, msg_fee, None
            fee_paise = rupees_to_paise(monthly_fee_val)
        elif batch_id:
            batch = db.batches.find_one({"batch_id": batch_id})
            fee_paise = batch.get("default_monthly_fee", 150000) if batch else 150000
        else:
            settings = db.settings.find_one({"_id": "global"}) or {}
            fee_paise = settings.get("default_monthly_fee", 150000)

        ok_day, due_day = ValidationService.validate_due_day(data.get("fee_due_day") or 5)

        raw_adm_date = str(data.get("admission_date", "")).strip()
        admission_date = parse_indian_date(raw_adm_date) if raw_adm_date else datetime.now().strftime("%Y-%m-%d")

        student_doc = {
            "student_id": student_id,
            "full_name": full_name,
            "phone": clean_phone,
            "parent_name": str(data.get("parent_name", "")).strip(),
            "parent_phone": clean_parent_phone,
            "address": str(data.get("address", "")).strip(),
            "batch_id": batch_id,
            "admission_date": admission_date,
            "monthly_fee_paise": fee_paise,
            "fee_due_day": due_day,
            "advance_balance_paise": 0,
            "status": data.get("status", "Active"),
            "notes": str(data.get("notes", "")).strip(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        db.students.insert_one(student_doc)

        # Generate fee dues from admission month through current month
        StudentService._generate_initial_dues(student_doc)

        student_doc["_id"] = str(student_doc.get("_id"))
        student_doc["monthly_fee_rupees"] = paise_to_rupees(fee_paise)
        return True, f"Student {full_name} ({student_id}) enrolled successfully.", student_doc

    @staticmethod
    def _generate_initial_dues(student):
        db = get_db()
        student_id = student["student_id"]
        adm_date_str = student["admission_date"]
        fee_paise = student.get("monthly_fee_paise", 0)
        due_day = student.get("fee_due_day", 5)

        try:
            start_dt = datetime.strptime(adm_date_str[:7], "%Y-%m")
        except Exception:
            start_dt = datetime.now()

        current_dt = datetime.now()
        year = start_dt.year
        month = start_dt.month
        today_str = current_dt.strftime("%Y-%m-%d")

        while (year < current_dt.year) or (year == current_dt.year and month <= current_dt.month):
            month_year = f"{year:04d}-{month:02d}"
            due_date = f"{year:04d}-{month:02d}-{due_day:02d}"
            
            existing = db.fee_dues.find_one({"student_id": student_id, "month_year": month_year})
            if not existing:
                status = "Overdue" if due_date < today_str else "Pending"
                db.fee_dues.insert_one({
                    "student_id": student_id,
                    "month_year": month_year,
                    "amount_due_paise": fee_paise,
                    "paid_amount_paise": 0,
                    "balance_paise": fee_paise,
                    "due_date": due_date,
                    "status": status,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                })

            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

    @staticmethod
    def get_student_by_id(student_id):
        if not student_id:
            return None
        db = get_db()
        student = db.students.find_one({"student_id": student_id})
        if not student:
            return None
            
        student["_id"] = str(student.get("_id"))
        student["monthly_fee_rupees"] = paise_to_rupees(student.get("monthly_fee_paise", 0))
        student["advance_balance_rupees"] = paise_to_rupees(student.get("advance_balance_paise", 0))
        student["formatted_admission_date"] = format_date_indian(student.get("admission_date", ""))
        
        batch = db.batches.find_one({"batch_id": student.get("batch_id")})
        student["batch_name"] = batch.get("batch_name", "Unassigned") if batch else "Unassigned"
        student["course_name"] = batch.get("course_name", "") if batch else ""
        return student

    @staticmethod
    def update_student(student_id, data):
        if not student_id or not data:
            return False, "Invalid update data."
        
        db = get_db()
        existing = db.students.find_one({"student_id": student_id})
        if not existing:
            return False, "Student not found."

        update_fields = {"updated_at": datetime.now(timezone.utc)}

        if "full_name" in data:
            full_name = str(data["full_name"]).strip()
            ok_name, msg_name = ValidationService.validate_name(full_name, "Student full name")
            if not ok_name:
                return False, msg_name
            update_fields["full_name"] = full_name

        if "phone" in data:
            ok_p, msg_p, clean_phone = ValidationService.validate_indian_phone(data["phone"], "Student phone", required=True)
            if not ok_p:
                return False, msg_p
            dup = db.students.find_one({"phone": clean_phone, "status": "Active", "student_id": {"$ne": student_id}})
            if dup:
                return False, f"Phone '{clean_phone}' is already in use by active student '{dup['full_name']}'."
            update_fields["phone"] = clean_phone

        if "parent_name" in data:
            update_fields["parent_name"] = str(data["parent_name"]).strip()

        if "parent_phone" in data:
            raw_pp = str(data["parent_phone"]).strip()
            if raw_pp:
                ok_pp, msg_pp, clean_pp = ValidationService.validate_indian_phone(raw_pp, "Parent phone", required=False)
                if not ok_pp:
                    return False, msg_pp
                update_fields["parent_phone"] = clean_pp
            else:
                update_fields["parent_phone"] = ""

        if "address" in data:
            update_fields["address"] = str(data["address"]).strip()
        if "batch_id" in data:
            update_fields["batch_id"] = str(data["batch_id"]).strip()
        if "status" in data:
            update_fields["status"] = str(data["status"]).strip()
        if "notes" in data:
            update_fields["notes"] = str(data["notes"]).strip()
            
        if "fee_due_day" in data:
            ok_day, due_day = ValidationService.validate_due_day(data["fee_due_day"])
            if ok_day:
                update_fields["fee_due_day"] = due_day

        if "monthly_fee" in data or "monthly_fee_rupees" in data:
            val = data.get("monthly_fee") or data.get("monthly_fee_rupees")
            ok_amt, msg_amt = ValidationService.validate_amount(val, "Monthly fee", min_val=0.0, max_val=500000.0)
            if not ok_amt:
                return False, msg_amt
            update_fields["monthly_fee_paise"] = rupees_to_paise(val)

        db.students.update_one({"student_id": student_id}, {"$set": update_fields})
        return True, "Student updated successfully."

    @staticmethod
    def delete_or_archive_student(student_id):
        if not student_id:
            return False, "Student ID is required."
        
        db = get_db()
        student = db.students.find_one({"student_id": student_id})
        if not student:
            return False, "Student not found."

        has_payments = db.payments.count_documents({"student_id": student_id}) > 0
        has_paid_dues = db.fee_dues.count_documents({"student_id": student_id, "paid_amount_paise": {"$gt": 0}}) > 0

        if has_payments or has_paid_dues:
            db.students.update_one(
                {"student_id": student_id},
                {"$set": {
                    "status": "Archived",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            return True, f"Student '{student_id}' has financial history. Record has been safely archived for audit compliance."
        else:
            db.fee_dues.delete_many({"student_id": student_id})
            db.students.delete_one({"student_id": student_id})
            return True, f"Student '{student_id}' deleted successfully."
