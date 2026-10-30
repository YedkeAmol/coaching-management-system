import re
from datetime import datetime

class ValidationService:
    @staticmethod
    def validate_indian_phone(phone_str, field_name="Phone number", required=True):
        if not phone_str:
            if required:
                return False, f"{field_name} is required.", ""
            return True, "", ""
            
        cleaned = re.sub(r"[\s\-\(\)\.]", "", str(phone_str).strip())
        if cleaned.startswith("+91"):
            cleaned = cleaned[3:]
        elif cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        elif cleaned.startswith("0") and len(cleaned) == 11:
            cleaned = cleaned[1:]

        if not re.match(r"^[6-9]\d{9}$", cleaned):
            return False, f"{field_name} must be a valid 10-digit Indian mobile number (e.g. 9876543210).", cleaned
        return True, "", cleaned

    @staticmethod
    def validate_name(name_str, field_name="Name", min_len=2, max_len=80):
        if not name_str or not str(name_str).strip():
            return False, f"{field_name} cannot be empty."
        name = str(name_str).strip()
        if len(name) < min_len:
            return False, f"{field_name} must be at least {min_len} characters long."
        if len(name) > max_len:
            return False, f"{field_name} cannot exceed {max_len} characters."
        if not re.search(r"[a-zA-Z]", name):
            return False, f"{field_name} must contain letters."
        return True, ""

    @staticmethod
    def validate_amount(amount, field_name="Amount", min_val=1.0, max_val=1000000.0):
        if amount is None or amount == "":
            return False, f"{field_name} is required."
        try:
            val = float(str(amount).replace(",", "").replace("₹", "").strip())
        except (ValueError, TypeError):
            return False, f"{field_name} must be a valid numeric amount."
        
        if val < min_val:
            return False, f"{field_name} must be at least ₹{min_val:.2f}."
        if val > max_val:
            return False, f"{field_name} cannot exceed ₹{max_val:,.2f}."
        return True, ""

    @staticmethod
    def validate_due_day(due_day):
        try:
            day = int(due_day)
            if 1 <= day <= 28:
                return True, day
        except (ValueError, TypeError):
            pass
        return False, 5

    @staticmethod
    def validate_date(date_str, field_name="Date"):
        if not date_str or not str(date_str).strip():
            return True, ""
        s = str(date_str).strip()
        # Accept YYYY-MM-DD or DD-MM-YYYY
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(s, fmt)
                return True, dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return False, f"{field_name} must be in YYYY-MM-DD or DD-MM-YYYY format."
