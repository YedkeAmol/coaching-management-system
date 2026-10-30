import io
import csv
from datetime import datetime, timedelta
from database import (
    get_db,
    rupees_to_paise,
    paise_to_rupees,
    format_inr,
    format_date_indian,
    parse_indian_date
)
from services.fee_service import FeeService

class ReportService:
    @staticmethod
    def get_dashboard_data():
        db = get_db()
        current_ym = datetime.now().strftime("%Y-%m")

        # 1. Total Active Students
        total_students = db.students.count_documents({"status": "Active"})

        # 2. Monthly Collection
        monthly_payments = list(db.payments.find({
            "payment_date": {"$regex": f"^{current_ym}"},
            "is_reversed": {"$ne": True}
        }))
        monthly_collection_paise = sum(p.get("amount_paise", 0) for p in monthly_payments)

        # 3. Overall Outstanding
        active_student_ids = [s["student_id"] for s in db.students.find({"status": "Active"}, {"student_id": 1})]
        outstanding_dues = list(db.fee_dues.find({
            "student_id": {"$in": active_student_ids},
            "balance_paise": {"$gt": 0}
        }))
        overall_outstanding_paise = sum(d.get("balance_paise", 0) for d in outstanding_dues)

        # 4. Unpaid Students Count
        unpaid_student_ids = set(d["student_id"] for d in outstanding_dues)
        unpaid_students_count = len(unpaid_student_ids)

        # 5. Recent Payments
        recent_payments = list(db.payments.find({"is_reversed": {"$ne": True}}).sort("payment_date", -1).limit(6))
        for p in recent_payments:
            p["_id"] = str(p.get("_id"))
            p["amount_rupees"] = paise_to_rupees(p.get("amount_paise", 0))
            p["formatted_amount"] = format_inr(p.get("amount_paise", 0))
            p["formatted_payment_date"] = format_date_indian(p.get("payment_date", ""))

        # 6. Top Defaulters
        defaulters = FeeService.get_pending_defaulters()[:5]

        # 7. Collection Trend (Last 6 Months)
        trend_labels = []
        trend_values = []
        now = datetime.now()
        for i in range(5, -1, -1):
            # calculate year and month
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            ym_str = f"{y:04d}-{m:02d}"
            label = datetime(y, m, 1).strftime("%b %y")
            trend_labels.append(label)

            month_pays = list(db.payments.find({
                "payment_date": {"$regex": f"^{ym_str}"},
                "is_reversed": {"$ne": True}
            }))
            total_m_paise = sum(p.get("amount_paise", 0) for p in month_pays)
            trend_values.append(paise_to_rupees(total_m_paise))

        # 8. Payment Methods Breakdown
        methods = ["UPI", "Cash", "Bank Transfer", "Other"]
        method_counts = {}
        for m in methods:
            total_paise = sum(p.get("amount_paise", 0) for p in db.payments.find({
                "payment_method": m,
                "is_reversed": {"$ne": True}
            }))
            method_counts[m] = paise_to_rupees(total_paise)

        return {
            "total_students": total_students,
            "monthly_collection_paise": monthly_collection_paise,
            "monthly_collection_rupees": paise_to_rupees(monthly_collection_paise),
            "formatted_monthly_collection": format_inr(monthly_collection_paise),
            "overall_outstanding_paise": overall_outstanding_paise,
            "overall_outstanding_rupees": paise_to_rupees(overall_outstanding_paise),
            "formatted_overall_outstanding": format_inr(overall_outstanding_paise),
            "unpaid_students_count": unpaid_students_count,
            "recent_payments": recent_payments,
            "recent_defaulters": defaulters,
            "collection_trend": {
                "labels": trend_labels,
                "values": trend_values,
                "amounts": trend_values
            },
            "payment_methods": {
                "labels": list(method_counts.keys()),
                "values": list(method_counts.values()),
                "amounts": list(method_counts.values())
            }
        }

    @staticmethod
    def get_collection_report(start_date=None, end_date=None, payment_method=None, batch_id=None):
        db = get_db()
        query = {"is_reversed": {"$ne": True}}

        if payment_method and payment_method.lower() != "all":
            query["payment_method"] = payment_method

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = parse_indian_date(start_date)
            if end_date:
                date_filter["$lte"] = parse_indian_date(end_date)
            query["payment_date"] = date_filter

        if batch_id and batch_id.lower() != "all":
            query["batch_id"] = batch_id

        payments = list(db.payments.find(query).sort("payment_date", -1))

        formatted_list = []
        total_paise = 0
        for p in payments:
            paise = p.get("amount_paise", 0)
            total_paise += paise
            formatted_list.append({
                "receipt_no": p.get("receipt_no"),
                "payment_date": format_date_indian(p.get("payment_date")),
                "raw_date": p.get("payment_date"),
                "student_id": p.get("student_id"),
                "student_name": p.get("student_name", "N/A"),
                "batch_name": p.get("batch_name", "N/A"),
                "batch_id": p.get("batch_id"),
                "payment_method": p.get("payment_method"),
                "reference_no": p.get("reference_no") or "N/A",
                "amount_paise": paise,
                "amount_rupees": paise_to_rupees(paise),
                "formatted_amount": format_inr(paise)
            })

        return {
            "payments": formatted_list,
            "total_amount_paise": total_paise,
            "total_amount_rupees": paise_to_rupees(total_paise),
            "formatted_total": format_inr(total_paise),
            "count": len(formatted_list)
        }

    @staticmethod
    def get_batch_summary_report():
        db = get_db()
        batches = list(db.batches.find({}))
        summary = []

        for b in batches:
            bid = b["batch_id"]
            students = list(db.students.find({"batch_id": bid, "status": "Active"}))
            student_count = len(students)
            monthly_expected = sum(s.get("monthly_fee_paise", 0) for s in students)

            # Collections from this batch
            payments = list(db.payments.find({"batch_id": bid, "is_reversed": {"$ne": True}}))
            total_collected = sum(p.get("amount_paise", 0) for p in payments)

            # Unpaid balance
            sids = [s["student_id"] for s in students]
            dues = list(db.fee_dues.find({"student_id": {"$in": sids}, "balance_paise": {"$gt": 0}}))
            outstanding = sum(d.get("balance_paise", 0) for d in dues)

            summary.append({
                "batch_id": bid,
                "batch_name": b.get("batch_name"),
                "course_name": b.get("course_name", "General"),
                "student_count": student_count,
                "monthly_expected_paise": monthly_expected,
                "monthly_expected_rupees": paise_to_rupees(monthly_expected),
                "formatted_monthly_expected": format_inr(monthly_expected),
                "total_collected_paise": total_collected,
                "total_collected_rupees": paise_to_rupees(total_collected),
                "formatted_total_collected": format_inr(total_collected),
                "outstanding_paise": outstanding,
                "outstanding_rupees": paise_to_rupees(outstanding),
                "formatted_outstanding": format_inr(outstanding)
            })

        summary.sort(key=lambda x: x["student_count"], reverse=True)
        return summary

    @staticmethod
    def get_admission_report(start_date=None, end_date=None, batch_id=None):
        db = get_db()
        query = {}

        if batch_id and batch_id.lower() != "all":
            query["batch_id"] = batch_id

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = parse_indian_date(start_date)
            if end_date:
                date_filter["$lte"] = parse_indian_date(end_date)
            query["admission_date"] = date_filter

        students = list(db.students.find(query).sort("admission_date", -1))
        batches_map = {b["batch_id"]: b["batch_name"] for b in db.batches.find({})}

        admissions = []
        for s in students:
            admissions.append({
                "student_id": s["student_id"],
                "full_name": s.get("full_name"),
                "phone": s.get("phone"),
                "parent_name": s.get("parent_name", "N/A"),
                "parent_phone": s.get("parent_phone", "N/A"),
                "batch_id": s.get("batch_id"),
                "batch_name": batches_map.get(s.get("batch_id"), "Unassigned"),
                "admission_date": format_date_indian(s.get("admission_date")),
                "monthly_fee_rupees": paise_to_rupees(s.get("monthly_fee_paise", 0)),
                "formatted_monthly_fee": format_inr(s.get("monthly_fee_paise", 0)),
                "status": s.get("status", "Active")
            })

        return admissions

    @staticmethod
    def generate_csv(headers, rows):
        """Generates UTF-8 BOM CSV text for seamless opening in Microsoft Excel and Numbers."""
        output = io.StringIO()
        # Write UTF-8 BOM for Excel
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return output.getvalue()
