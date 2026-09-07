"""
BlockSync AI — Synthetic Data Generator (Stage 2)
Generates realistic maintenance task data for Engineering, Signal, and
Traction departments, plus corridor availability and train schedules.
Saves everything as CSV files for Stage 3 to load into Supabase.
"""

import random
from datetime import datetime, timedelta, time
import csv
import os

# Fixed seed = same data every time you run this (makes debugging much easier)
random.seed(42)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------
# STEP A: Define corridor sections (the shared "map" of the railway)
# ---------------------------------------------------------------
SECTIONS = [f"SEC-{str(i).zfill(2)}" for i in range(1, 19)]  # SEC-01 to SEC-18

# ---------------------------------------------------------------
# STEP B: Deliberate overlap sections — guarantees the merge logic
# has real cross-department cases to demonstrate later
# ---------------------------------------------------------------
OVERLAP_SECTIONS = ["SEC-03", "SEC-07", "SEC-09", "SEC-12", "SEC-15", "SEC-16"]

# ---------------------------------------------------------------
# STEP C: Defect types per department (realistic railway terms)
# ---------------------------------------------------------------
DEFECT_TYPES = {
    "Engineering": ["Rail crack", "Ballast deficiency", "Rail wear", "Track misalignment", "Joint gap defect"],
    "Signal": ["Signal relay fault", "Point machine malfunction", "Cable insulation fault", "Signal lamp failure", "Interlocking fault"],
    "Traction": ["OHE wire wear", "Insulator damage", "Feeder cable fault", "Traction pole corrosion", "Circuit breaker fault"],
}

DEPT_PREFIX = {"Engineering": "TMS", "Signal": "SMMS", "Traction": "TDMS"}

TASKS_PER_DEPT = 18
TOTAL_TASKS = TASKS_PER_DEPT * 3  # 54 total

today = datetime.now().date()

# ---------------------------------------------------------------
# STEP D: Generate maintenance_tasks.csv
# ---------------------------------------------------------------
tasks = []
task_counter = 1

for dept in ["Engineering", "Signal", "Traction"]:
    for i in range(TASKS_PER_DEPT):
        task_id = f"{DEPT_PREFIX[dept]}-{str(task_counter).zfill(4)}"
        task_counter += 1

        # Force some tasks into deliberate overlap sections (guarantees merge candidates)
        if i < 3:  # first 3 tasks per department go into overlap sections
            section = random.choice(OVERLAP_SECTIONS)
        else:
            section = random.choice(SECTIONS)

        defect_type = random.choice(DEFECT_TYPES[dept])

        # Severity distribution: mostly 2-3, some 4, a deliberate few 5s
        if i < 2:  # exactly 2 severity-5 (safety-critical) tasks per department = 6 total
            severity = 5
        else:
            severity = random.choices([1, 2, 3, 4], weights=[10, 35, 35, 20])[0]

        days_ago = random.randint(0, 30)
        reported_date = today - timedelta(days=days_ago)

        # Duration scales roughly with severity (bigger problems take longer to fix)
        est_duration_hrs = round(random.uniform(1.5, 3.0) + severity * 0.6, 1)

        tasks.append({
            "task_id": task_id,
            "department": dept,
            "corridor_section": section,
            "defect_type": defect_type,
            "severity": severity,
            "reported_date": reported_date.isoformat(),
            "est_duration_hrs": est_duration_hrs,
            "status": "Pending",
            "reported_by": "",       # filled properly in Stage 9 (login system)
            "rolled_over": "False",
        })

with open(os.path.join(OUTPUT_DIR, "maintenance_tasks.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=tasks[0].keys())
    writer.writeheader()
    writer.writerows(tasks)

print(f"maintenance_tasks.csv created: {len(tasks)} tasks")
print(f"   Severity-5 (safety-critical) tasks: {sum(1 for t in tasks if t['severity'] == 5)}")

# ---------------------------------------------------------------
# STEP E: Generate corridor_availability.csv
# Typical railway maintenance windows: late night, when passenger
# traffic is lowest (e.g., 00:00-04:00 or 23:00-05:00)
# ---------------------------------------------------------------
availability = []
for section in SECTIONS:
    # 2-3 availability windows per section across the coming week
    num_windows = random.randint(2, 3)
    for w in range(num_windows):
        day_offset = random.randint(0, 6)
        avail_date = today + timedelta(days=day_offset)
        start_hour = random.choice([0, 1, 22, 23])
        start_t = time(hour=start_hour % 24, minute=0)
        end_hour = (start_hour + random.choice([3, 4, 5])) % 24
        end_t = time(hour=end_hour, minute=0)

        availability.append({
            "section_id": section,
            "date": avail_date.isoformat(),
            "available_from": start_t.strftime("%H:%M:%S"),
            "available_to": end_t.strftime("%H:%M:%S"),
        })

with open(os.path.join(OUTPUT_DIR, "corridor_availability.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=availability[0].keys())
    writer.writeheader()
    writer.writerows(availability)

print(f"corridor_availability.csv created: {len(availability)} windows")

# ---------------------------------------------------------------
# STEP F: Generate train_schedule.csv
# Mix of passenger (more frequent) and goods (less frequent) trains
# ---------------------------------------------------------------
train_schedule = []
train_counter = 10001

for section in SECTIONS:
    # each section gets 2-3 train passages over the week
    num_trains = random.randint(2, 3)
    for t in range(num_trains):
        day_offset = random.randint(0, 6)
        train_date = today + timedelta(days=day_offset)
        hour = random.randint(5, 21)  # daytime running hours
        minute = random.choice([0, 15, 30, 45])
        arrival = datetime.combine(train_date, time(hour, minute))
        departure = arrival + timedelta(minutes=random.randint(2, 8))

        train_type = "Passenger" if random.random() < 0.7 else "Goods"

        train_schedule.append({
            "train_id": str(train_counter),
            "section_id": section,
            "arrival_time": arrival.isoformat(sep=" "),
            "departure_time": departure.isoformat(sep=" "),
            "type": train_type,
        })
        train_counter += 1

with open(os.path.join(OUTPUT_DIR, "train_schedule.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=train_schedule[0].keys())
    writer.writeheader()
    writer.writerows(train_schedule)

print(f"train_schedule.csv created: {len(train_schedule)} train entries")

# ---------------------------------------------------------------
# STEP G: Basic validation (per Critical Success Factor: check before scaling)
# ---------------------------------------------------------------
task_ids = [t["task_id"] for t in tasks]
assert len(task_ids) == len(set(task_ids)), "Duplicate task_id found!"
assert all(t["est_duration_hrs"] > 0 for t in tasks), "Negative/zero duration found!"
assert all(1 <= t["severity"] <= 5 for t in tasks), "Invalid severity value found!"

print("\nAll validation checks passed.")
print(f"Summary: {TOTAL_TASKS} tasks across 3 departments, {len(SECTIONS)} corridor sections")
print(f"Overlap sections for merge demo: {OVERLAP_SECTIONS}")