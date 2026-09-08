const BASE_URL = "http://localhost:8000";

async function get(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error on ${path}: ${res.status}`);
  return res.json();
}

export const api = {
  getTasks: () => get("/tasks"),
  getWeeklySchedule: () => get("/schedule/weekly"),
  getMonthlySchedule: () => get("/schedule/monthly"),
  getMergeLog: () => get("/merge-log"),
  getRolloverLog: () => get("/rollover-log"),
  getMetrics: () => get("/metrics"),
};