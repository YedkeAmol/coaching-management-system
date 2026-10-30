from datetime import datetime, timezone
from database import get_db, rupees_to_paise, paise_to_rupees
from services.validation_service import ValidationService

class BatchService:
    @staticmethod
    def get_all_batches(active_only=False):
        db = get_db()
        query = {"is_active": True} if active_only else {}
        batches = list(db.batches.find(query).sort("batch_id", 1))
        
        # Attach active student counts and rupee values
        for b in batches:
            b["_id"] = str(b.get("_id"))
            b["default_monthly_fee_rupees"] = paise_to_rupees(b.get("default_monthly_fee", 0))
            b["student_count"] = db.students.count_documents({
                "batch_id": b.get("batch_id"),
                "status": "Active"
            })
        return batches

    @staticmethod
    def create_batch(data):
        if not data:
            return False, "Batch data is required.", None
            
        bname = str(data.get("batch_name", "")).strip()
        ok_n, msg_n = ValidationService.validate_name(bname, "Batch name", min_len=2)
        if not ok_n:
            return False, msg_n, None

        monthly_fee = data.get("default_monthly_fee") or data.get("monthly_fee") or 0
        ok_amt, msg_amt = ValidationService.validate_amount(monthly_fee, "Default monthly fee", min_val=0.0, max_val=500000.0)
        if not ok_amt:
            return False, msg_amt, None
        
        db = get_db()
        # Generate batch ID if not provided
        batch_id = data.get("batch_id")
        if not batch_id:
            count = db.batches.count_documents({}) + 1
            batch_id = f"BAT-{count:02d}"
            # Ensure unique
            while db.batches.find_one({"batch_id": batch_id}):
                count += 1
                batch_id = f"BAT-{count:02d}"

        course_id = data.get("course_id", "")
        course_name = data.get("course_name", "")
        if course_id and not course_name:
            crs = db.courses.find_one({"course_id": course_id})
            if crs:
                course_name = crs.get("course_name", "")

        fee_paise = rupees_to_paise(monthly_fee)

        batch_doc = {
            "batch_id": batch_id,
            "batch_name": data.get("batch_name", "").strip(),
            "course_id": course_id,
            "course_name": course_name,
            "schedule": data.get("schedule", "").strip(),
            "default_monthly_fee": fee_paise,
            "is_active": bool(data.get("is_active", True)),
            "created_at": datetime.now(timezone.utc)
        }

        db.batches.insert_one(batch_doc)
        batch_doc["_id"] = str(batch_doc.get("_id"))
        batch_doc["default_monthly_fee_rupees"] = paise_to_rupees(fee_paise)
        batch_doc["student_count"] = 0
        return True, "Batch created successfully.", batch_doc

    @staticmethod
    def update_batch(batch_id, data):
        if not batch_id or not data:
            return False, "Invalid batch data."
        
        db = get_db()
        existing = db.batches.find_one({"batch_id": batch_id})
        if not existing:
            return False, "Batch not found."

        update_fields = {}
        if "batch_name" in data:
            update_fields["batch_name"] = str(data["batch_name"]).strip()
        if "schedule" in data:
            update_fields["schedule"] = str(data["schedule"]).strip()
        if "course_id" in data:
            course_id = str(data["course_id"]).strip()
            update_fields["course_id"] = course_id
            crs = db.courses.find_one({"course_id": course_id})
            if crs:
                update_fields["course_name"] = crs.get("course_name", "")
        if "is_active" in data:
            update_fields["is_active"] = bool(data["is_active"])
        if "default_monthly_fee" in data:
            update_fields["default_monthly_fee"] = rupees_to_paise(data["default_monthly_fee"])
        elif "monthly_fee" in data:
            update_fields["default_monthly_fee"] = rupees_to_paise(data["monthly_fee"])

        if update_fields:
            db.batches.update_one({"batch_id": batch_id}, {"$set": update_fields})
        return True, "Batch updated successfully."

    @staticmethod
    def get_all_courses(active_only=False):
        db = get_db()
        query = {"is_active": True} if active_only else {}
        courses = list(db.courses.find(query).sort("course_id", 1))
        for c in courses:
            c["_id"] = str(c.get("_id"))
            c["default_fee_rupees"] = paise_to_rupees(c.get("default_fee", 0))
        return courses

    @staticmethod
    def create_course(data):
        if not data:
            return False, "Course data is required.", None
        
        cname = str(data.get("course_name", "")).strip()
        ok_n, msg_n = ValidationService.validate_name(cname, "Course title", min_len=2)
        if not ok_n:
            return False, msg_n, None

        fee = data.get("default_fee") or data.get("fee") or 0
        ok_amt, msg_amt = ValidationService.validate_amount(fee, "Default course fee", min_val=0.0, max_val=500000.0)
        if not ok_amt:
            return False, msg_amt, None
        
        db = get_db()
        course_id = data.get("course_id")
        if not course_id:
            count = db.courses.count_documents({}) + 101
            course_id = f"CRS-{count}"
            while db.courses.find_one({"course_id": course_id}):
                count += 1
                course_id = f"CRS-{count}"

        fee_paise = rupees_to_paise(fee)

        course_doc = {
            "course_id": course_id,
            "course_name": data.get("course_name", "").strip(),
            "description": data.get("description", "").strip(),
            "duration": data.get("duration", "1 Year").strip(),
            "default_fee": fee_paise,
            "is_active": bool(data.get("is_active", True)),
            "created_at": datetime.now(timezone.utc)
        }
        db.courses.insert_one(course_doc)
        course_doc["_id"] = str(course_doc.get("_id"))
        course_doc["default_fee_rupees"] = paise_to_rupees(fee_paise)
        return True, "Course created successfully.", course_doc

    @staticmethod
    def update_course(course_id, data):
        if not course_id or not data:
            return False, "Invalid course data."
        
        db = get_db()
        existing = db.courses.find_one({"course_id": course_id})
        if not existing:
            return False, "Course not found."

        update_fields = {}
        if "course_name" in data:
            update_fields["course_name"] = str(data["course_name"]).strip()
        if "description" in data:
            update_fields["description"] = str(data["description"]).strip()
        if "duration" in data:
            update_fields["duration"] = str(data["duration"]).strip()
        if "is_active" in data:
            update_fields["is_active"] = bool(data["is_active"])
        if "default_fee" in data:
            update_fields["default_fee"] = rupees_to_paise(data["default_fee"])

        if update_fields:
            db.courses.update_one({"course_id": course_id}, {"$set": update_fields})
        return True, "Course updated successfully."
