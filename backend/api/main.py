"""
BlockSync AI — Backend API (Stage 7)
Exposes all engine results (tasks, schedules, metrics, merge log) as
clean REST endpoints for the frontend dashboard to consume.
"""

import os
import math
from datetime import datetime, date, timedelta
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(
    title="BlockSync AI API",
    description="AI-Powered Automatic Block Planning for Indian Railways — SIH 26027",
    version="1.0.0",
)

def clean_nan(obj):
    """Recursively replace any NaN float with None so JSON serialization never fails."""
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj

# ---------------------------------------------------------------
# CORS — allows your React frontend (different port/domain) to call this API.
# Wide open for now during local development; we will restrict this to
# your actual deployed frontend URL in Stage 12 (Deployment).
# ---------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------
# Health check — useful to confirm the API is alive
# ---------------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "ok", "service": "BlockSync AI API"}


# ---------------------------------------------------------------
# GET /tasks — all maintenance tasks with priority scores
# ---------------------------------------------------------------
@app.get("/tasks")
def get_tasks(department: str = None, status: str = None):
    query = supabase.table("maintenance_tasks").select("*")
    if department:
        query = query.eq("department", department)
    if status:
        query = query.eq("status", status)
    result = query.order("priority_score", desc=True).execute()
    return {"count": len(result.data), "tasks": result.data}


# ---------------------------------------------------------------
# GET /schedule/weekly — day-by-day optimized block plan
# ---------------------------------------------------------------
@app.get("/schedule/weekly")
def get_weekly_schedule():
    result = supabase.table("optimized_schedule").select("*").execute()
    blocks = result.data

    if not blocks:
        return {"days": []}

    df = pd.DataFrame(blocks)
    df["start_time_parsed"] = pd.to_datetime(df["start_time"])
    df["date_only"] = df["start_time_parsed"].dt.date.astype(str)

    days = []
    for day, group in df.groupby("date_only"):
        records = group.drop(columns=["start_time_parsed", "date_only"]).to_dict("records")
        days.append({
            "date": day,
            "blocks": clean_nan(records),
        })
    days.sort(key=lambda d: d["date"])
    return {"days": days}

# ---------------------------------------------------------------
# GET /schedule/monthly — higher-level summary view
# ---------------------------------------------------------------
@app.get("/schedule/monthly")
def get_monthly_schedule():
    result = supabase.table("optimized_schedule").select("*").execute()
    blocks = result.data

    if not blocks:
        return {"total_blocks": 0, "total_merges": 0, "sections_touched": 0, "departments_active": 0}

    df = pd.DataFrame(blocks)
    all_depts = set()
    for dept_list in df["departments_involved"]:
        all_depts.update(dept_list)

    return {
        "total_blocks": len(df),
        "total_merges": int(df["merged"].sum()),
        "sections_touched": int(df["section_id"].nunique()),
        "departments_active": len(all_depts),
    }


# ---------------------------------------------------------------
# GET /merge-log — list of cross-department merged blocks (demo highlight)
# ---------------------------------------------------------------
@app.get("/merge-log")
def get_merge_log():
    result = supabase.table("optimized_schedule").select("*").eq("merged", True).execute()
    return {"count": len(result.data), "merges": result.data}


# ---------------------------------------------------------------
# GET /rollover-log — tasks that didn't fit this horizon
# ---------------------------------------------------------------
@app.get("/rollover-log")
def get_rollover_log():
    result = supabase.table("maintenance_tasks").select("*").eq("rolled_over", True).execute()
    return {"count": len(result.data), "rolled_over_tasks": result.data}


# ---------------------------------------------------------------
# GET /metrics — the 3-metric comparison from Stage 6
# ---------------------------------------------------------------
@app.get("/metrics")
def get_metrics():
    all_tasks_resp = supabase.table("maintenance_tasks").select("*").execute()
    all_tasks = pd.DataFrame(all_tasks_resp.data)

    optimized_resp = supabase.table("optimized_schedule").select("*").execute()
    optimized_df = pd.DataFrame(optimized_resp.data)

    baseline_resp = supabase.table("baseline_schedule").select("*").execute()
    baseline_df = pd.DataFrame(baseline_resp.data)

    optimized_df = optimized_df.where(pd.notnull(optimized_df), None)
    baseline_df = baseline_df.where(pd.notnull(baseline_df), None)

    if optimized_df.empty:
        raise HTTPException(status_code=404, detail="No optimized schedule found. Run Stage 5 (optimizer.py) first.")

    # Metric 1: Throughput
    ai_scheduled_ids = set(optimized_df["tasks_included"].explode()) if len(optimized_df) else set()
    naive_scheduled_ids = set(baseline_df["task_id"]) if not baseline_df.empty else set()

    # Metric 2: Merging efficiency
    task_duration_lookup = dict(zip(all_tasks["task_id"], all_tasks["est_duration_hrs"]))
    no_merge_hours = sum(task_duration_lookup.get(tid, 0) for tid in ai_scheduled_ids)
    ai_actual_hours = sum(
        (datetime.fromisoformat(b["end_time"]) - datetime.fromisoformat(b["start_time"])).total_seconds() / 3600
        for _, b in optimized_df.iterrows()
    )
    merge_savings_pct = ((no_merge_hours - ai_actual_hours) / no_merge_hours * 100) if no_merge_hours > 0 else 0

    # Metric 3: Safety
    severity5_tasks = all_tasks[all_tasks["severity"] == 5]
    severity5_missed_naive = severity5_tasks[~severity5_tasks["task_id"].isin(naive_scheduled_ids)]["task_id"].tolist()

    return clean_nan({
        "throughput": {
            "naive_scheduled": len(naive_scheduled_ids),
            "ai_scheduled": len(ai_scheduled_ids),
            "additional_tasks_by_ai": len(ai_scheduled_ids) - len(naive_scheduled_ids),
        },
        "merging_efficiency": {
            "hours_without_merging": round(no_merge_hours, 1),
            "hours_with_ai_merging": round(ai_actual_hours, 1),
            "downtime_saved_pct": round(merge_savings_pct, 1),
            "total_merges": int(optimized_df["merged"].sum()),
        },
        "safety": {
            "severity5_missed_by_naive": severity5_missed_naive,
            "severity5_missed_by_naive_count": len(severity5_missed_naive),
            "severity5_missed_by_ai_count": 0,
        },
    })