# Coaching Management System (CMS)

A production-grade, full-stack coaching and tuition management web application built with **Python (Flask)**, **MongoDB (PyMongo)**, **Vanilla ES6+ JavaScript**, and **Tailwind CSS**.

Designed specifically for personal coaching classes, private tutors, and coaching academies to handle student admissions, batch scheduling, fee dues, advance credits, payment receipts, defaulter tracking, and comprehensive financial reports.

---

## 🌟 Key Features

1. **Dashboard Overview**:
   - Total active students, monthly collection, overall outstanding fees, unpaid students count.
   - Monthly Collection Trend bar chart & Payment Methods breakdown (Chart.js).
   - Recent payment transaction stream and overdue defaulters list.
   - One-click quick action buttons (*Record Payment*, *Add Student*, *Pending Fees*).

2. **Student Management**:
   - Unique auto-generated Student IDs (`STU-YYYY-XXXX`).
   - Detailed profiles: personal information, parent contact, assigned batch, custom monthly tuition fee, and fee due day.
   - Live search by Name, Student ID, or Phone number, with batch and status filters.
   - Safe archiving: When a student with financial history is deleted, their record is preserved as *Archived* to maintain legal audit trail compliance.

3. **Batches & Courses**:
   - Create and configure batches with schedules (e.g. *Mon, Wed, Fri 4:00 PM - 5:30 PM*) and default monthly fees.
   - Support for individual student fee overrides that differ from the batch default.
   - Active student enrollment counters per batch.

4. **Fee Management & Ledger Accounting**:
   - **Integer Paise Storage**: Monetary amounts are stored in integer paise (e.g., ₹1,500.00 = `150000` paise) ensuring zero floating-point arithmetic errors.
   - **Chronological Ledger Allocation**: Payments automatically settle the oldest unpaid monthly due first.
   - **Advance Payments**: Unallocated excess payments are carried forward as *Advance Credit* and automatically offset future dues as new months arrive.
   - **Statuses**: `Paid`, `Partially Paid`, `Pending`, `Overdue`, and `Advance`.
   - **Controlled Reversal**: Audit-compliant reversal flow for bounced cheques or erroneous entries with required reason tracking (never silently deletes transactions).

5. **Monthly Fee Tracking**:
   - Dedicated monthly grid with quick month/year picker.
   - Displays Fee Due, Amount Paid, Remaining Balance, Due Date, and Status for every enrolled student.
   - Collect fees directly from any table row with instant modal.

6. **Payment Receipts & PDF Export**:
   - Unique server-generated receipt numbers (`REC-YYYYMM-XXXX`).
   - Printable receipt modal and dedicated standalone printable receipt page formatted with `@media print` CSS for saving as PDF or direct thermal/desktop printing.

7. **Pending Fees & Defaulters**:
   - Identifies students with unpaid fees past their due date.
   - Tracks oldest unpaid due date, days overdue, and severity badges.
   - Direct export to CSV and printable report format.

8. **Reports & Analytics**:
   - Date-range fee collection reports.
   - Batch-wise student & revenue summary.
   - Admissions log report.
   - 1-click UTF-8 BOM CSV exports for Excel compatibility.

9. **Security & Authentication**:
   - Werkzeug secure password hashing (`generate_password_hash` / `check_password_hash`).
   - Flask session management with HTTP-only cookies.
   - Protected routes and authenticated REST API endpoints.

---

## 💻 Tech Stack

- **Backend**: Python 3.11+, Flask 3.0+
- **Database**: MongoDB (via PyMongo 4.8+)
- **Fallback DB**: Automatic in-memory database (`mongomock`) allows immediate out-of-the-box local testing even before MongoDB is running!
- **Frontend**: HTML5, Vanilla JavaScript (ES6+), Tailwind CSS, Lucide Icons, Chart.js
- **Testing**: Pytest 8.2+

---

## 🚀 Setup & Installation (Windows PowerShell)

### 1. Prerequisites
- **Python 3.11+** installed on your system.
- **MongoDB Community Server** (Local) OR a free **MongoDB Atlas** cloud cluster.

### 2. Navigate to Project Directory
Open **Windows PowerShell** and navigate to the project directory:
```powershell
cd "C:\Users\kuldeep rajput\.gemini\antigravity\scratch\coaching-management-system"
```

### 3. Create & Activate Virtual Environment
```powershell
# Create venv
python -m venv venv

# Activate venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell displays an execution policy restriction, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Inside `.env`, verify or customize your settings:
```ini
SECRET_KEY=coaching-super-secure-secret-key-2026
FLASK_DEBUG=True
PORT=5000

# For Local MongoDB:
MONGO_URI=mongodb://localhost:27017/coaching_db

# For MongoDB Atlas (Cloud):
# MONGO_URI=mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/coaching_db?retryWrites=true&w=majority

DB_NAME=coaching_db

DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123
DEFAULT_ADMIN_NAME=Admin Principal
```

> **Note on MongoDB Connection**:
> The application includes an **intelligent database manager**. If local MongoDB is running, it connects automatically. If MongoDB is not yet running, it smoothly falls back to development in-memory mode so you can test all features immediately without crashes!

### 6. (Optional) Seed Sample Demonstration Data
To populate realistic batches, students, fee dues, and payment transactions:
```powershell
python seed_demo_data.py
```

### 7. Run the Application
```powershell
python app.py
```
Output:
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### 8. Access the System
Open your web browser and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

**Default Administrator Credentials**:
- **Username**: `admin`
- **Password**: `admin123`

---

## 🧪 Running Automated Tests

Run the full automated test suite with pytest:
```powershell
.\venv\Scripts\python.exe -m pytest -v
```

All 13 test suites verify:
- Accurate paise conversion and Indian currency notation (`₹1,25,000.00`).
- The exact prompt fee scenario (October ₹1,000 due, ₹600 paid, ₹400 balance -> ₹400 paid, ₹0 balance -> November ₹1,000 due -> ₹1,000 overall outstanding).
- Advance payments and automatic future credit consumption.
- Prevention of duplicate payment submissions.
- Controlled reversal maintaining complete audit trails.
- Input validation on phone numbers and negative amounts.
- Route authentication and session protections.
- Safe archiving when deleting students who have payment history.

---

## 📦 Setting Up Real MongoDB

### Option A: Free Cloud Database (MongoDB Atlas)
1. Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) and create a free M0 cluster.
2. In **Database Access**, create a user (e.g. `coaching_admin`).
3. In **Network Access**, allow IP access (e.g. your IP or `0.0.0.0/0`).
4. Click **Connect** > **Drivers** > copy the connection string.
5. In `.env`, paste your URI:
   ```ini
   MONGO_URI=mongodb+srv://coaching_admin:your_password@cluster0.abcde.mongodb.net/coaching_db?retryWrites=true&w=majority
   ```
6. Restart `python app.py`.

### Option B: Local MongoDB on Windows
1. Download MongoDB Community MSI from [mongodb.com/try/download/community](https://www.mongodb.com/try/download/community).
2. Install as a "Network Service" and include MongoDB Compass if desired.
3. Start the service in PowerShell:
   ```powershell
   Start-Service MongoDB
   ```

---

## 💾 MongoDB Backup and Restore

### Backup Database (`mongodump`):
```powershell
mongodump --uri="mongodb://localhost:27017/coaching_db" --out="C:\backup\coaching_$(Get-Date -Format 'yyyyMMdd')"
```

### Restore Database (`mongorestore`):
```powershell
mongorestore --uri="mongodb://localhost:27017/coaching_db" --drop "C:\backup\coaching_20261028\coaching_db"
```
