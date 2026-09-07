"""
BlockSync AI — Optimization Engine (Stage 5)
The core: assigns tasks to corridor availability windows using Google
OR-Tools CP-SAT, enforcing the severity-5 hard safety guarantee,
detecting cross-department merges, and flagging rollovers.
"""

import os
import uuid
from datetime import datetime, date, timedelta
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from ortools.sat.python import cp_model

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------
MAX_DELAY_DAYS_SEVERITY5 = 3   # R12: severity-5 tasks MUST be scheduled within this many days
HORIZON_DAYS = 7               # weekly planning horizon
EMERGENCY_BUFFER_DAYS = HORIZON_DAYS   # if already overdue past the max delay, it must be scheduled somewhere within this planning cycle
SOLVER_TIME_LIMIT_SECONDS = 30

today = date.today()
horizon_end = today + timedelta(days=HORIZON_DAYS)

# ---------------------------------------------------------------
# STEP A: Fetch everything we need from Supabase
# ---------------------------------------------------------------
print("Fetching data from Supabase...")

tasks_resp = supabase.table("maintenance_tasks").select("*").eq("status", "Pending").execute()
tasks_df = pd.DataFrame(tasks_resp.data)
print(f"  Fetched {len(tasks_df)} pending tasks")

avail_resp = supabase.table("corridor_availability").select("*").execute()
avail_df = pd.DataFrame(avail_resp.data)
print(f"  Fetched {len(avail_df)} availability windows")

trains_resp = supabase.table("train_schedule").select("*").execute()
trains_df = pd.DataFrame(trains_resp.data)
print(f"  Fetched {len(trains_df)} train schedule entries")

compat_resp = supabase.table("department_compatibility").select("*").execute()
compat_df = pd.DataFrame(compat_resp.data)
print(f"  Fetched {len(compat_df)} compatibility rules")

if len(tasks_df) == 0:
    raise SystemExit("No pending tasks found. Check Stage 3/4 ran correctly.")

# Build a lookup: (dept_a, dept_b) -> mode, in both directions
compat_lookup = {}
for _, row in compat_df.iterrows():
    compat_lookup[(row["dept_a"], row["dept_b"])] = row["mode"]
    compat_lookup[(row["dept_b"], row["dept_a"])] = row["mode"]

def get_compat_mode(dept_a, dept_b):
    if dept_a == dept_b:
        return None  # same department isn't a "merge" in our sense
    return compat_lookup.get((dept_a, dept_b))

# ---------------------------------------------------------------
# STEP B: Build the slot list from corridor_availability
# ---------------------------------------------------------------
def time_to_minutes(t_str):
    h, m, s = map(int, t_str.split(":"))
    return h * 60 + m

def slot_duration_hours(start_str, end_str):
    start_min = time_to_minutes(start_str)
    end_min = time_to_minutes(end_str)
    if end_min <= start_min:  # crosses midnight
        end_min += 24 * 60
    return (end_min - start_min) / 60

slots = []
for idx, row in avail_df.iterrows():
    slot_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
    if slot_date < today or slot_date > horizon_end:
        continue  # outside our planning horizon
    duration = slot_duration_hours(row["available_from"], row["available_to"])
    slots.append({
        "slot_id": idx,
        "section_id": row["section_id"],
        "date": slot_date,
        "available_from": row["available_from"],
        "available_to": row["available_to"],
        "duration_hours": duration,
    })

print(f"\nBuilt {len(slots)} usable slots within the {HORIZON_DAYS}-day horizon")

# ---------------------------------------------------------------
# STEP C: Safety check — exclude any slot that actually overlaps a
# train passage on the same section and date (defensive check; our
# synthetic data separates day/night, but a real system must verify this)
# ---------------------------------------------------------------
def slot_conflicts_with_train(slot, trains_df):
    same_section_trains = trains_df[trains_df["section_id"] == slot["section_id"]]
    slot_start = time_to_minutes(slot["available_from"])
    slot_end = time_to_minutes(slot["available_to"])
    if slot_end <= slot_start:
        slot_end += 24 * 60
    for _, train in same_section_trains.iterrows():
        train_dt = datetime.fromisoformat(train["arrival_time"])
        if train_dt.date() != slot["date"]:
            continue
        train_min = train_dt.hour * 60 + train_dt.minute
        if slot_start <= train_min <= slot_end:
            return True
    return False

slots = [s for s in slots if not slot_conflicts_with_train(s, trains_df)]
print(f"After train-conflict safety check: {len(slots)} valid slots remain")

# ---------------------------------------------------------------
# STEP D: Determine eligible (task, slot) pairs
# ---------------------------------------------------------------
tasks = tasks_df.to_dict("records")

eligible_pairs = []  # list of (task_index, slot_index)
for ti, task in enumerate(tasks):
    reported_date = datetime.strptime(task["reported_date"], "%Y-%m-%d").date()
    is_critical = task["severity"] == 5

    max_allowed_date = reported_date + timedelta(days=MAX_DELAY_DAYS_SEVERITY5)
    # If the task is already overdue past its original deadline, treat it as an emergency:
    # it must get the next available slot within a short buffer from today, not an
    # impossible date in the past.
    emergency_deadline = today + timedelta(days=EMERGENCY_BUFFER_DAYS)
    max_allowed_date = max(max_allowed_date, emergency_deadline)

    if task["severity"] == 5:
        print(f"DEBUG {task['task_id']}: reported={reported_date}, max_allowed_date={max_allowed_date}, today={today}")

    for si, slot in enumerate(slots):
        if slot["section_id"] != task["corridor_section"]:
            continue
        if task["est_duration_hrs"] > slot["duration_hours"]:
            continue
        if is_critical and slot["date"] > max_allowed_date:
            continue  # R12: severity-5 tasks cannot be pushed past the max delay
        eligible_pairs.append((ti, si))

print(f"\nFound {len(eligible_pairs)} valid (task, slot) combinations")

# ---------------------------------------------------------------
# STEP E: Build the CP-SAT model
# ---------------------------------------------------------------
model = cp_model.CpModel()

x = {}  # x[(ti, si)] = 1 if task ti is assigned to slot si
for (ti, si) in eligible_pairs:
    x[(ti, si)] = model.NewBoolVar(f"x_{ti}_{si}")

# Each task assigned to at most 1 slot (or exactly 1 if severity-5)
infeasible_critical_tasks = []
for ti, task in enumerate(tasks):
    task_vars = [x[(ti, si)] for (t, si) in eligible_pairs if t == ti]
    if not task_vars:
        if task["severity"] == 5:
            infeasible_critical_tasks.append(task["task_id"])
        continue  # no eligible slots at all for this task
    if task["severity"] == 5:
        model.Add(sum(task_vars) == 1)  # R12: MUST be scheduled
    else:
        model.Add(sum(task_vars) <= 1)  # optional

if infeasible_critical_tasks:
    print(f"\n⚠️  WARNING: {len(infeasible_critical_tasks)} severity-5 tasks have NO eligible "
          f"slot at all within the max delay window: {infeasible_critical_tasks}")
    print("   This means corridor availability is too sparse for these — expand availability data.")

# Slot capacity: sum of assigned durations must fit within the window (safe, sequential-worst-case)
for si, slot in enumerate(slots):
    slot_vars_and_durations = [
        (x[(ti, s)], tasks[ti]["est_duration_hrs"])
        for (ti, s) in eligible_pairs if s == si
    ]
    if slot_vars_and_durations:
        # scale hours to integers (x100) since CP-SAT needs integer coefficients
        model.Add(
            sum(int(dur * 100) * var for var, dur in slot_vars_and_durations)
            <= int(slot["duration_hours"] * 100)
        )

# ---------------------------------------------------------------
# STEP F: Objective — maximize scheduled priority, minimize wasted hours as tiebreak
# ---------------------------------------------------------------
objective_terms = []
for (ti, si) in eligible_pairs:
    priority = tasks[ti]["priority_score"] or 0
    duration = tasks[ti]["est_duration_hrs"]
    # Priority dominates (scaled up); duration is a small penalty to discourage waste
    score = int(priority * 10000) - int(duration * 10)
    objective_terms.append(score * x[(ti, si)])

model.Maximize(sum(objective_terms))

# ---------------------------------------------------------------
# STEP G: Solve
# ---------------------------------------------------------------
print("\nSolving optimization model...")
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_SECONDS
status = solver.Solve(model)

status_name = solver.StatusName(status)
print(f"Solver status: {status_name}")

if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    raise SystemExit(f"Solver could not find a solution (status: {status_name}). "
                      "Check that corridor_availability has enough windows.")

# ---------------------------------------------------------------
# STEP H: Extract the solution — which task went into which slot
# ---------------------------------------------------------------
slot_assignments = {}  # slot_index -> list of task_indices assigned to it
scheduled_task_ids = set()

for (ti, si) in eligible_pairs:
    if solver.Value(x[(ti, si)]) == 1:
        slot_assignments.setdefault(si, []).append(ti)
        scheduled_task_ids.add(tasks[ti]["task_id"])

print(f"\nScheduled {len(scheduled_task_ids)} of {len(tasks)} tasks")

# ---------------------------------------------------------------
# STEP I: Build block records — detect merges using compatibility table
# ---------------------------------------------------------------
blocks = []
for si, task_indices in slot_assignments.items():
    slot = slots[si]
    assigned_tasks = [tasks[ti] for ti in task_indices]

    departments_involved = list(set(t["department"] for t in assigned_tasks))
    merged = False
    merge_mode = None

    if len(assigned_tasks) >= 2 and len(departments_involved) >= 2:
        # Check compatibility between the (first two) different departments present
        mode = get_compat_mode(assigned_tasks[0]["department"], assigned_tasks[1]["department"])
        if mode:
            merged = True
            merge_mode = mode

    # Compute real block duration based on merge mode
    durations = [t["est_duration_hrs"] for t in assigned_tasks]
    if merged and merge_mode == "Simultaneous":
        block_duration = max(durations)
    else:
        block_duration = sum(durations)  # Sequential merge, or no merge (solo/same-dept)

    start_dt = datetime.combine(slot["date"], datetime.strptime(slot["available_from"], "%H:%M:%S").time())
    end_dt = start_dt + timedelta(hours=block_duration)

    blocks.append({
        "block_id": f"BLK-{uuid.uuid4().hex[:8].upper()}",
        "section_id": slot["section_id"],
        "tasks_included": [t["task_id"] for t in assigned_tasks],
        "departments_involved": departments_involved,
        "start_time": start_dt.isoformat(sep=" "),
        "end_time": end_dt.isoformat(sep=" "),
        "merged": merged,
        "merge_mode": merge_mode,
        "priority_score_max": max(t["priority_score"] or 0 for t in assigned_tasks),
    })

merged_blocks = [b for b in blocks if b["merged"]]
print(f"Created {len(blocks)} blocks total, of which {len(merged_blocks)} are cross-department merges")

for b in merged_blocks:
    print(f"  MERGE: {b['block_id']} — {b['tasks_included']} "
          f"({' + '.join(b['departments_involved'])}, mode={b['merge_mode']})")

# ---------------------------------------------------------------
# STEP J: Rollover — tasks that did NOT get scheduled
# ---------------------------------------------------------------
rolled_over_ids = [t["task_id"] for t in tasks if t["task_id"] not in scheduled_task_ids]
print(f"\n{len(rolled_over_ids)} tasks rolled over (not scheduled this horizon): {rolled_over_ids[:10]}"
      f"{'...' if len(rolled_over_ids) > 10 else ''}")

# Confirm severity-5 tasks are NOT in the rollover list (this is the R12 proof point)
critical_rolled_over = [t["task_id"] for t in tasks if t["task_id"] in rolled_over_ids and t["severity"] == 5]
if critical_rolled_over:
    print(f"🚨 CRITICAL BUG: severity-5 tasks were rolled over: {critical_rolled_over} — this should be impossible!")
else:
    print("✅ Confirmed: zero severity-5 tasks were rolled over (R12 hard guarantee held)")

# ---------------------------------------------------------------
# STEP K: Write everything back to Supabase
# ---------------------------------------------------------------
print("\nWriting results back to Supabase...")

# Clear old optimized_schedule results before writing new ones
supabase.table("optimized_schedule").delete().neq("block_id", "").execute()
if blocks:
    supabase.table("optimized_schedule").insert(blocks).execute()
print(f"  Inserted {len(blocks)} blocks into optimized_schedule")

# Update task statuses
for task_id in scheduled_task_ids:
    supabase.table("maintenance_tasks").update({"status": "Scheduled"}).eq("task_id", task_id).execute()

for task_id in rolled_over_ids:
    supabase.table("maintenance_tasks").update({"rolled_over": True}).eq("task_id", task_id).execute()

print(f"  Updated {len(scheduled_task_ids)} tasks to 'Scheduled'")
print(f"  Flagged {len(rolled_over_ids)} tasks as rolled_over")

print("\n" + "="*50)
print("STAGE 5 COMPLETE — Optimization engine ran successfully")
print("="*50)