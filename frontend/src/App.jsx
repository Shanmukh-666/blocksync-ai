import { useEffect, useState } from "react";
import { api } from "./api";
import MetricsPanel from "./components/MetricsPanel";
import GanttChart from "./components/GanttChart";
import MergeLog from "./components/MergeLog";
import RolloverLog from "./components/RolloverLog";

export default function App() {
  const [metrics, setMetrics] = useState(null);
  const [weeklySchedule, setWeeklySchedule] = useState(null);
  const [mergeLog, setMergeLog] = useState(null);
  const [rolloverLog, setRolloverLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadAll() {
      try {
        const [m, w, mg, r] = await Promise.all([
          api.getMetrics(),
          api.getWeeklySchedule(),
          api.getMergeLog(),
          api.getRolloverLog(),
        ]);
        setMetrics(m);
        setWeeklySchedule(w);
        setMergeLog(mg);
        setRolloverLog(r);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadAll();
  }, []);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading BlockSync AI dashboard...</div>;
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center text-red-500 text-center px-4">
        <div>
          <p className="font-bold mb-2">Failed to load data.</p>
          <p className="text-sm">{error}</p>
          <p className="text-sm mt-2 text-gray-500">Is your backend running on http://localhost:8000?</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 p-3 sm:p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">BlockSync AI</h1>
        <p className="text-gray-500">AI-Powered Automatic Block Planning — SIH 26027</p>
      </header>

      <MetricsPanel metrics={metrics} />
      <div className="mb-6">
        <GanttChart weeklySchedule={weeklySchedule} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <MergeLog mergeLog={mergeLog} />
        <RolloverLog rolloverLog={rolloverLog} />
      </div>
    </div>
  );
}