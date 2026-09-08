export default function RolloverLog({ rolloverLog }) {
  if (!rolloverLog) return null;

  return (
    <div className="bg-white rounded-xl shadow p-5">
      <h2 className="text-lg font-bold text-gray-800 mb-3">
        Rolled Over Tasks <span className="text-amber-600">({rolloverLog.count})</span>
      </h2>
      <p className="text-xs text-gray-500 mb-3">
        Did not fit this horizon — carried forward with rising urgency, never silently dropped.
      </p>
      <div className="flex flex-wrap gap-2">
        {rolloverLog.rolled_over_tasks.map((t) => (
          <span
            key={t.task_id}
            className="text-xs bg-amber-50 text-amber-800 border border-amber-200 rounded-full px-2.5 py-1"
            title={`${t.department} — ${t.defect_type} (severity ${t.severity})`}
          >
            {t.task_id}
          </span>
        ))}
      </div>
    </div>
  );
}