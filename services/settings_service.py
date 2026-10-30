from datetime import datetime, timezone
from database import get_db, rupees_to_paise, paise_to_rupees

class SettingsService:
    @staticmethod
    def get_settings():
        db = get_db()
        settings = db.settings.find_one({"_id": "global"})
        if not settings:
            settings = {
                "_id": "global",
                "institute_name": "Apex Coaching Academy",
                "contact_number": "+91 98765 43210",
                "email": "contact@apexacademy.com",
                "address": "104, Education Hub, Near City Square, New Delhi, India",
                "default_monthly_fee": 150000,
                "default_fee_due_day": 5,
                "payment_methods": ["Cash", "UPI", "Bank Transfer", "Other"],
                "currency_symbol": "₹",
                "date_format": "DD-MM-YYYY"
            }
        # Provide float representation for forms
        settings["default_monthly_fee_rupees"] = paise_to_rupees(settings.get("default_monthly_fee", 150000))
        return settings

    @staticmethod
    def update_settings(data):
        if not data:
            return False, "No data provided."
        
        db = get_db()
        update_fields = {
            "updated_at": datetime.now(timezone.utc)
        }
        
        if "institute_name" in data:
            update_fields["institute_name"] = str(data["institute_name"]).strip()
        if "contact_number" in data:
            update_fields["contact_number"] = str(data["contact_number"]).strip()
        if "email" in data:
            update_fields["email"] = str(data["email"]).strip()
        if "address" in data:
            update_fields["address"] = str(data["address"]).strip()
        if "default_fee_due_day" in data:
            try:
                due_day = int(data["default_fee_due_day"])
                if 1 <= due_day <= 28:
                    update_fields["default_fee_due_day"] = due_day
            except (ValueError, TypeError):
                pass
        if "default_monthly_fee" in data:
            update_fields["default_monthly_fee"] = rupees_to_paise(data["default_monthly_fee"])
        elif "default_monthly_fee_rupees" in data:
            update_fields["default_monthly_fee"] = rupees_to_paise(data["default_monthly_fee_rupees"])

        if "payment_methods" in data:
            methods = data["payment_methods"]
            if isinstance(methods, str):
                methods = [m.strip() for m in methods.split(",") if m.strip()]
            if isinstance(methods, list) and methods:
                update_fields["payment_methods"] = methods

        db.settings.update_one(
            {"_id": "global"},
            {"$set": update_fields},
            upsert=True
        )
        return True, "Settings updated successfully."
