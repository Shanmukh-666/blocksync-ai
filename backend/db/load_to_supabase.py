"""
BlockSync AI — ETL Script (Stage 3)
Reads the 3 synthetic CSV files from Stage 2, validates them, and loads
them directly into your live Supabase database.
"""

import os
import csv
from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------
# STEP A: Load environment variables from .env
# ---------------------------------------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Missing SUPABASE_URL or SUPABASE_KEY in .env file. "
        "Check backend/.env has both values filled in correctly."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# ---------------------------------------------------------------
# STEP B: Helper to read a CSV into a list of dicts
# ---------------------------------------------------------------
def read_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------
# STEP C: Load maintenance_tasks.csv
# ---------------------------------------------------------------
print("Loading maintenance_tasks.csv...")
tasks = read_csv("maintenance_tasks.csv")

# --- Validation before inserting (Critical Success Factor: never skip this) ---
task_ids = [t["task_id"] for t in tasks]
assert len(task_ids) == len(set(task_ids)), "VALIDATION FAILED: duplicate task_id found"
assert all(float(t["est_duration_hrs"]) > 0 for t in tasks), "VALIDATION FAILED: non-positive duration found"
assert all(1 <= int(t["severity"]) <= 5 for t in tasks), "VALIDATION FAILED: severity out of range"
print(f"  Validation passed for {len(tasks)} tasks")

# Clean up types for Supabase (CSV reads everything as strings)
rows = []
for t in tasks:
    rows.append({
        "task_id": t["task_id"],
        "department": t["department"],
        "corridor_section": t["corridor_section"],
        "defect_type": t["defect_type"],
        "severity": int(t["severity"]),
        "reported_date": t["reported_date"],
        "est_duration_hrs": float(t["est_duration_hrs"]),
        "status": t["status"],
        "reported_by": t["reported_by"] if t["reported_by"] else None,
        "rolled_over": t["rolled_over"] == "True",
    })

# upsert = insert, or update if task_id already exists (safe to re-run this script)
result = supabase.table("maintenance_tasks").upsert(rows).execute()
print(f"  Inserted/updated {len(result.data)} rows into maintenance_tasks")

# ---------------------------------------------------------------
# STEP D: Load corridor_availability.csv
# ---------------------------------------------------------------
print("\nLoading corridor_availability.csv...")
availability = read_csv("corridor_availability.csv")

rows = []
for a in availability:
    rows.append({
        "section_id": a["section_id"],
        "date": a["date"],
        "available_from": a["available_from"],
        "available_to": a["available_to"],
    })

# Clear old rows first (this table has no natural unique key to upsert against safely)
supabase.table("corridor_availability").delete().neq("id", 0).execute()
result = supabase.table("corridor_availability").insert(rows).execute()
print(f"  Inserted {len(result.data)} rows into corridor_availability")

# ---------------------------------------------------------------
# STEP E: Load train_schedule.csv
# ---------------------------------------------------------------
print("\nLoading train_schedule.csv...")
trains = read_csv("train_schedule.csv")

rows = []
for t in trains:
    rows.append({
        "train_id": t["train_id"],
        "section_id": t["section_id"],
        "arrival_time": t["arrival_time"],
        "departure_time": t["departure_time"],
        "type": t["type"],
    })

supabase.table("train_schedule").delete().neq("id", 0).execute()
result = supabase.table("train_schedule").insert(rows).execute()
print(f"  Inserted {len(result.data)} rows into train_schedule")

# ---------------------------------------------------------------
# STEP F: Verify department_compatibility already has data (from Stage 1 SQL)
# ---------------------------------------------------------------
print("\nVerifying department_compatibility table...")
compat = supabase.table("department_compatibility").select("*").execute()
assert len(compat.data) == 3, (
    f"Expected 3 rows in department_compatibility, found {len(compat.data)}. "
    "Re-run the INSERT statement from Stage 1 Step 6 in Supabase SQL Editor."
)
print(f"  Confirmed: {len(compat.data)} compatibility rules present")

print("\n" + "="*50)
print("ETL COMPLETE — all data is now live in Supabase")
print("="*50)