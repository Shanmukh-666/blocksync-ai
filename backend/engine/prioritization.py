"""
BlockSync AI — Priority Scoring Engine (Stage 4, Part B)
Combines severity, urgency, impact (rule-based) with the ML escalation
risk score into one final priority_score per task, then writes it back
to Supabase.
"""

import os
from datetime import datetime, date
import pandas as pd
import joblib
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")

# ---------------------------------------------------------------
# STEP A: Load the trained ML model + encoders from Stage 4 Part A
# ---------------------------------------------------------------
model = joblib.load(os.path.join(MODELS_DIR, "escalation_model.joblib"))
dept_encoder = joblib.load(os.path.join(MODELS_DIR, "dept_encoder.joblib"))
defect_encoder = joblib.load(os.path.join(MODELS_DIR, "defect_encoder.joblib"))

# ---------------------------------------------------------------
# STEP B: Fetch tasks and train schedule from Supabase
# ---------------------------------------------------------------
print("Fetching data from Supabase...")
tasks_response = supabase.table("maintenance_tasks").select("*").eq("status", "Pending").execute()
tasks = pd.DataFrame(tasks_response.data)
print(f"  Fetched {len(tasks)} pending tasks")

trains_response = supabase.table("train_schedule").select("*").execute()
trains = pd.DataFrame(trains_response.data)
print(f"  Fetched {len(trains)} train schedule entries")

if len(tasks) == 0:
    raise SystemExit("No pending tasks found — check Stage 3 loaded data correctly.")

# ---------------------------------------------------------------
# STEP C: Compute trains_passing_per_day for each corridor section
# ---------------------------------------------------------------
trains_per_section = trains.groupby("section_id").size()
# Rough per-day estimate: total entries were spread across ~7 days
trains_per_section_per_day = (trains_per_section / 7).to_dict()
max_trains_per_day = max(trains_per_section_per_day.values()) if trains_per_section_per_day else 1

def get_trains_per_day(section_id):
    return trains_per_section_per_day.get(section_id, 1)  # default 1 if section has no trains recorded

# ---------------------------------------------------------------
# STEP D: Compute each factor for every task
# ---------------------------------------------------------------
today = date.today()

def compute_row(row):
    severity = int(row["severity"])
    reported_date = datetime.strptime(row["reported_date"], "%Y-%m-%d").date()
    days_since_reported = (today - reported_date).days
    trains_per_day = get_trains_per_day(row["corridor_section"])

    # --- Rule-based factors ---
    severity_normalized = severity / 5
    urgency_normalized = min(days_since_reported / 30, 1.0)
    impact_normalized = trains_per_day / max_trains_per_day

    # --- ML factor: escalation risk prediction ---
    try:
        dept_encoded = dept_encoder.transform([row["department"]])[0]
    except ValueError:
        dept_encoded = 0  # unseen department fallback
    try:
        defect_encoded = defect_encoder.transform([row["defect_type"]])[0]
    except ValueError:
        defect_encoded = 0  # unseen defect type fallback

    features = pd.DataFrame([{
        "severity": severity,
        "days_since_reported": days_since_reported,
        "trains_per_day": trains_per_day,
        "department_encoded": dept_encoded,
        "defect_type_encoded": defect_encoded,
    }])
    escalation_risk_score = model.predict_proba(features)[0][1]  # probability of class "1" (escalated)

    # --- Final combined priority score ---
    priority_score = (
        0.4 * severity_normalized
        + 0.25 * urgency_normalized
        + 0.2 * impact_normalized
        + 0.15 * escalation_risk_score
    )

    return pd.Series({
        "priority_score": round(priority_score, 4),
        "escalation_risk_score": round(escalation_risk_score, 4),
        "days_since_reported": days_since_reported,
    })

print("\nComputing priority scores...")
computed = tasks.apply(compute_row, axis=1)

# Drop the old empty columns fetched from Supabase before adding the computed ones,
# to avoid duplicate column names
tasks = tasks.drop(columns=["priority_score", "escalation_risk_score"], errors="ignore")
tasks = pd.concat([tasks, computed], axis=1)

# ---------------------------------------------------------------
# STEP E: Sort and display the ranked list (sanity check before writing back)
# ---------------------------------------------------------------
ranked = tasks.sort_values("priority_score", ascending=False)

print("\nTop 10 highest-priority tasks:")
print(ranked[["task_id", "department", "severity", "days_since_reported", "escalation_risk_score", "priority_score"]].head(10).to_string(index=False))

# ---------------------------------------------------------------
# STEP F: Write scores back to Supabase
# ---------------------------------------------------------------
print("\nWriting priority scores back to Supabase...")
for _, row in tasks.iterrows():
    supabase.table("maintenance_tasks").update({
        "priority_score": row["priority_score"],
        "escalation_risk_score": row["escalation_risk_score"],
    }).eq("task_id", row["task_id"]).execute()

print(f"Updated {len(tasks)} tasks with priority scores")
print("STAGE 4 PART B COMPLETE")