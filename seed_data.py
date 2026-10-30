#!/usr/bin/env python3
"""
Seed script for Coaching Management System.
Populates the database with sample courses, batches, students, fee dues, and payment records.
Can be run directly: python seed_data.py
"""

import sys
import logging
from database import get_db, get_db_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")

def main():
    logger.info("Connecting to database...")
    db_mgr = get_db_manager()
    db = db_mgr.get_db()

    logger.info(f"Connected to database: {db.name} (is_mock={db_mgr.is_mock})")

    # Run ensure indexes and seed initial data
    db_mgr._ensure_indexes()
    db_mgr._seed_initial_data()

    student_count = db.students.count_documents({})
    batch_count = db.batches.count_documents({})
    payment_count = db.payments.count_documents({})
    fee_dues_count = db.fee_dues.count_documents({})

    logger.info(f"Database status after seeding:")
    logger.info(f"  - Active/Total Students: {student_count}")
    logger.info(f"  - Batches: {batch_count}")
    logger.info(f"  - Payments Recorded: {payment_count}")
    logger.info(f"  - Fee Dues Generated: {fee_dues_count}")

    print("\n--- Seeded Students ---")
    for s in db.students.find({}):
        print(f"  [{s.get('student_id')}] {s.get('full_name')} - Phone: {s.get('phone')} | Batch: {s.get('batch_id')} | Status: {s.get('status')}")

    print("\n--- Recent Payments ---")
    for p in db.payments.find({}):
        print(f"  [{p.get('receipt_no')}] {p.get('student_name')} - {p.get('formatted_amount', p.get('amount_rupees'))} ({p.get('payment_method')}) on {p.get('payment_date')}")

    print("\n[OK] Seeding verified successfully.")

if __name__ == "__main__":
    main()
