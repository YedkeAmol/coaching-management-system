import os
import logging
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance = None

    def __init__(self, uri=None, db_name=None):
        global _db_manager
        self.uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/coaching_db")
        self.db_name = db_name or os.getenv("DB_NAME", "coaching_db")
        self.client = None
        self.db = None
        self.is_connected = False
        self.is_mock = False
        _db_manager = self
        self._init_connection()

    def _init_connection(self):
        try:
            # Short timeout to detect if local mongod is available
            test_client = MongoClient(self.uri, serverSelectionTimeoutMS=1500)
            test_client.admin.command('ping')
            self.client = test_client
            self.db = self.client[self.db_name]
            self.is_connected = True
            self.is_mock = False
            logger.info("Successfully connected to live MongoDB database.")
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            logger.warning(
                f"Live MongoDB connection failed ({e}). Falling back to in-memory database (mongomock) for seamless development/testing."
            )
            try:
                import mongomock
                self.client = mongomock.MongoClient()
                self.db = self.client[self.db_name]
                self.is_connected = True
                self.is_mock = True
                logger.info("Initialized mongomock fallback database.")
            except ImportError:
                self.is_connected = False
                logger.error("Neither MongoDB nor mongomock is available.")
                raise e

        if self.db is not None:
            self._ensure_indexes()
            self._seed_initial_data()

    def _ensure_indexes(self):
        try:
            # Users
            self.db.users.create_index("username", unique=True)
            # Students
            self.db.students.create_index("student_id", unique=True)
            self.db.students.create_index("phone")
            self.db.students.create_index("batch_id")
            self.db.students.create_index("status")
            # Courses
            self.db.courses.create_index("course_id", unique=True)
            # Batches
            self.db.batches.create_index("batch_id", unique=True)
            # Fee Dues - compound index on student_id and month_year
            self.db.fee_dues.create_index([("student_id", ASCENDING), ("month_year", ASCENDING)], unique=True)
            self.db.fee_dues.create_index("due_date")
            self.db.fee_dues.create_index("status")
            # Payments
            self.db.payments.create_index("receipt_no", unique=True)
            self.db.payments.create_index("student_id")
            self.db.payments.create_index([("payment_date", DESCENDING)])
            # Allocations
            self.db.payment_allocations.create_index("payment_id")
            self.db.payment_allocations.create_index("fee_due_id")
            self.db.payment_allocations.create_index("student_id")
            logger.info("Database indexes successfully verified.")
        except Exception as e:
            logger.warning(f"Note on index creation: {e}")

    def _seed_initial_data(self):
        try:
            # Seed default admin user if none exists
            if self.db.users.count_documents({}) == 0:
                admin_user = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
                admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
                admin_name = os.getenv("DEFAULT_ADMIN_NAME", "Administrator")
                self.db.users.insert_one({
                    "username": admin_user,
                    "password_hash": generate_password_hash(admin_pass),
                    "full_name": admin_name,
                    "role": "admin",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                })
                logger.info(f"Default admin user '{admin_user}' seeded.")

            # Seed default settings if none exists
            if self.db.settings.count_documents({"_id": "global"}) == 0:
                self.db.settings.insert_one({
                    "_id": "global",
                    "institute_name": "Apex Coaching Academy",
                    "contact_number": "+91 98765 43210",
                    "email": "contact@apexacademy.com",
                    "address": "104, Education Hub, Near City Square, New Delhi, India",
                    "default_monthly_fee": 150000,  # 1500.00 INR in paise
                    "default_fee_due_day": 5,        # 5th of every month
                    "payment_methods": ["Cash", "UPI", "Bank Transfer", "Other"],
                    "currency_symbol": "₹",
                    "date_format": "DD-MM-YYYY",
                    "updated_at": datetime.now(timezone.utc)
                })
                logger.info("Default institute settings seeded.")

            # Seed sample courses & batches if empty so user has realistic data to explore immediately
            if self.db.courses.count_documents({}) == 0:
                sample_courses = [
                    {
                        "course_id": "CRS-101",
                        "course_name": "Mathematics - Class 10 Board Prep",
                        "description": "Comprehensive preparation for Class 10 CBSE/State Board Mathematics",
                        "duration": "1 Year",
                        "default_fee": 150000,  # ₹1500.00
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc)
                    },
                    {
                        "course_id": "CRS-102",
                        "course_name": "Physics - Class 11 & 12 Foundation",
                        "description": "Mechanics, Electromagnetism, Optics and numerical practice for competitive exams",
                        "duration": "2 Years",
                        "default_fee": 200000,  # ₹2000.00
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc)
                    },
                    {
                        "course_id": "CRS-103",
                        "course_name": "Chemistry - JEE / NEET Booster",
                        "description": "Organic, Inorganic & Physical Chemistry with mock tests",
                        "duration": "1 Year",
                        "default_fee": 180000,  # ₹1800.00
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc)
                    }
                ]
                self.db.courses.insert_many(sample_courses)

            if self.db.batches.count_documents({}) == 0:
                sample_batches = [
                    {
                        "batch_id": "BAT-01",
                        "batch_name": "Class 10 Morning Achievers",
                        "course_id": "CRS-101",
                        "course_name": "Mathematics - Class 10 Board Prep",
                        "schedule": "Mon, Wed, Fri (7:00 AM - 8:30 AM)",
                        "default_monthly_fee": 150000,
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc)
                    },
                    {
                        "batch_id": "BAT-02",
                        "batch_name": "Class 12 Evening Champions",
                        "course_id": "CRS-102",
                        "course_name": "Physics - Class 11 & 12 Foundation",
                        "schedule": "Tue, Thu, Sat (5:00 PM - 6:30 PM)",
                        "default_monthly_fee": 200000,
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc)
                    },
                    {
                        "batch_id": "BAT-03",
                        "batch_name": "Class 12 Weekend JEE Intensive",
                        "course_id": "CRS-103",
                        "course_name": "Chemistry - JEE / NEET Booster",
                        "schedule": "Sat & Sun (10:00 AM - 1:00 PM)",
                        "default_monthly_fee": 180000,
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc)
                    }
                ]
                self.db.batches.insert_many(sample_batches)

            # Seed sample students if none exist
            if self.db.students.count_documents({}) == 0:
                self._seed_sample_students()

        except Exception as e:
            logger.warning(f"Note on initial seeding: {e}")

    def _seed_sample_students(self):
        try:
            from services.student_service import StudentService
            from services.payment_service import PaymentService

            students_data = [
                {
                    "full_name": "Aarav Sharma",
                    "phone": "9820112233",
                    "parent_name": "Rajesh Sharma",
                    "parent_phone": "9820112230",
                    "address": "B-42, Shanti Nagar, New Delhi",
                    "batch_id": "BAT-01",
                    "admission_date": "2026-08-01",
                    "monthly_fee": 1500.0,
                    "fee_due_day": 5,
                    "notes": "Targeting CBSE Board 95%+ and NTSE Stage 1"
                },
                {
                    "full_name": "Priya Patel",
                    "phone": "9833445566",
                    "parent_name": "Suresh Patel",
                    "parent_phone": "9833445560",
                    "address": "12/A, Navrangpura, Ahmedabad",
                    "batch_id": "BAT-02",
                    "admission_date": "2026-07-15",
                    "monthly_fee": 2000.0,
                    "fee_due_day": 5,
                    "notes": "Preparing for JEE Main & State CET"
                },
                {
                    "full_name": "Rohan Deshmukh",
                    "phone": "9844556677",
                    "parent_name": "Anand Deshmukh",
                    "parent_phone": "9844556670",
                    "address": "Flat 304, Shivneri Heights, Pune",
                    "batch_id": "BAT-01",
                    "admission_date": "2026-09-01",
                    "monthly_fee": 1500.0,
                    "fee_due_day": 10,
                    "notes": "Regular student, needs focus on Geometry"
                },
                {
                    "full_name": "Ananya Gupta",
                    "phone": "9855667788",
                    "parent_name": "Vikram Gupta",
                    "parent_phone": "9855667780",
                    "address": "Sector 14, Rohini, New Delhi",
                    "batch_id": "BAT-03",
                    "admission_date": "2026-08-10",
                    "monthly_fee": 1800.0,
                    "fee_due_day": 5,
                    "notes": "NEET aspirant, strong in Organic Chemistry"
                }
            ]

            created = []
            for s in students_data:
                ok, msg, stu = StudentService.create_student(s)
                if ok and stu:
                    created.append(stu)

            if len(created) >= 4:
                # 1. Aarav paid August & September (₹3000 total)
                PaymentService.record_payment({
                    "student_id": created[0]["student_id"],
                    "amount": 3000.0,
                    "payment_method": "UPI",
                    "payment_date": "2026-09-05",
                    "reference_no": "UPI-8291039481",
                    "notes": "Combined August and September fee clearance"
                })

                # 2. Priya paid July+August (₹4000) and September+October+Advance (₹4500)
                PaymentService.record_payment({
                    "student_id": created[1]["student_id"],
                    "amount": 4000.0,
                    "payment_method": "Bank Transfer",
                    "payment_date": "2026-08-04",
                    "reference_no": "IMPS-7192830192",
                    "notes": "July and August tuition fees"
                })
                PaymentService.record_payment({
                    "student_id": created[1]["student_id"],
                    "amount": 4500.0,
                    "payment_method": "UPI",
                    "payment_date": "2026-10-03",
                    "reference_no": "UPI-9102830192",
                    "notes": "September + October fees with ₹500 advance credit"
                })

                # 3. Rohan paid partial ₹1000 for September
                PaymentService.record_payment({
                    "student_id": created[2]["student_id"],
                    "amount": 1000.0,
                    "payment_method": "Cash",
                    "payment_date": "2026-09-10",
                    "notes": "Partial fee deposit by parent"
                })

                # 4. Ananya paid August & September (₹3600 total)
                PaymentService.record_payment({
                    "student_id": created[3]["student_id"],
                    "amount": 3600.0,
                    "payment_method": "UPI",
                    "payment_date": "2026-09-08",
                    "reference_no": "UPI-9810239481",
                    "notes": "August and September fees paid online"
                })

            logger.info("Sample students, dues and payments seeded successfully.")
        except Exception as e:
            logger.warning(f"Note on student seeding: {e}")

    def get_db(self):
        return self.db

    def get_client(self):
        return self.client


# Singleton getter
_db_manager = None

def get_db_manager(uri=None, db_name=None):
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(uri, db_name)
    return _db_manager

def get_db():
    return get_db_manager().get_db()

def set_db(db):
    """Allows test fixtures to set an isolated test database."""
    get_db_manager().db = db



# -------------------------------------------------------------------------
# Financial & Formatting Utilities (Paise, Indian Currency & Date Formats)
# -------------------------------------------------------------------------

def rupees_to_paise(amount_in_rupees) -> int:
    """
    Safely converts a rupee amount (float, int, or string) to integer paise.
    e.g. 1500.50 -> 150050, 1500 -> 150000
    Never uses lossy floating point operations.
    """
    if amount_in_rupees is None or amount_in_rupees == "":
        return 0
    try:
        if isinstance(amount_in_rupees, (int, float)):
            # Round to 2 decimal places before converting to integer paise
            return int(round(float(amount_in_rupees) * 100))
        cleaned = str(amount_in_rupees).strip().replace(",", "").replace("₹", "")
        if not cleaned:
            return 0
        return int(round(float(cleaned) * 100))
    except (ValueError, TypeError):
        return 0

def paise_to_rupees(amount_in_paise: int) -> float:
    """
    Converts integer paise to float rupees for display or calculation.
    e.g. 150050 -> 1500.50
    """
    if amount_in_paise is None:
        return 0.0
    try:
        return int(amount_in_paise) / 100.0
    except (ValueError, TypeError):
        return 0.0

def format_inr(amount_in_paise: int, include_symbol: bool = True) -> str:
    """
    Formats integer paise into standard Indian numbering format (e.g. ₹1,25,000.00).
    Negative amounts are displayed as -₹... or -...
    """
    if amount_in_paise is None:
        amount_in_paise = 0
    try:
        paise_val = int(amount_in_paise)
    except (ValueError, TypeError):
        paise_val = 0

    is_negative = paise_val < 0
    paise_abs = abs(paise_val)

    rupees_part = paise_abs // 100
    paise_part = paise_abs % 100

    rupees_str = str(rupees_part)
    
    # Format according to Indian numbering system (3 digits, then groups of 2)
    if len(rupees_str) <= 3:
        formatted_rupees = rupees_str
    else:
        last3 = rupees_str[-3:]
        remaining = rupees_str[:-3]
        groups = []
        while len(remaining) > 2:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.append(remaining)
        groups.reverse()
        formatted_rupees = ",".join(groups) + "," + last3

    result = f"{formatted_rupees}.{paise_part:02d}"
    symbol = "₹" if include_symbol else ""
    if is_negative:
        return f"-{symbol}{result}"
    return f"{symbol}{result}"

def format_date_indian(date_val) -> str:
    """
    Formats a date (string 'YYYY-MM-DD' or datetime) into Indian format 'DD-MM-YYYY'.
    """
    if not date_val:
        return ""
    try:
        if isinstance(date_val, str):
            clean_str = date_val.strip()
            # If already DD-MM-YYYY
            if len(clean_str) == 10 and clean_str[2] == '-' and clean_str[5] == '-':
                return clean_str
            dt = datetime.strptime(clean_str[:10], "%Y-%m-%d")
            return dt.strftime("%d-%m-%Y")
        elif hasattr(date_val, "strftime"):
            return date_val.strftime("%d-%m-%Y")
    except Exception:
        pass
    return str(date_val)

def parse_indian_date(date_str: str) -> str:
    """
    Converts 'DD-MM-YYYY' or 'YYYY-MM-DD' input into standard ISO 'YYYY-MM-DD' for DB storage.
    """
    if not date_str:
        return ""
    clean = str(date_str).strip()
    try:
        if len(clean) == 10:
            if clean[2] == '-' and clean[5] == '-':
                # DD-MM-YYYY
                dt = datetime.strptime(clean, "%d-%m-%Y")
                return dt.strftime("%Y-%m-%d")
            elif clean[4] == '-' and clean[7] == '-':
                # Already YYYY-MM-DD
                return clean
    except Exception:
        pass
    return clean
