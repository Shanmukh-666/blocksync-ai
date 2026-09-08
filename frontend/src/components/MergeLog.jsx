export default function MergeLog({ mergeLog }) {
  if (!mergeLog || mergeLog.count === 0) {
    return (
      <div className="bg-white rounded-xl shadow p-5">
        <h2 className="text-lg font-bold text-gray-800 mb-2">Cross-Department Merges</h2>
        <p className="text-gray-500 text-sm">No merges found.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow p-5">
      <h2 className="text-lg font-bold text-gray-800 mb-3">
        Cross-Department Merges <span className="text-emerald-600">({mergeLog.count})</span>
      </h2>
      <div className="space-y-2">
        {mergeLog.merges.map((m) => (
          <div key={m.block_id} className="flex items-center justify-between bg-emerald-50 rounded-lg px-3 py-2 text-sm">
            <div>
              <span className="font-medium text-gray-800">{m.tasks_included.join(" + ")}</span>
              <span className="text-gray-500 ml-2">({m.departments_involved.join(" + ")})</span>
            </div>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
              m.merge_mode === "Simultaneous" ? "bg-emerald-200 text-emerald-800" : "bg-amber-200 text-amber-800"
            }`}>
              {m.merge_mode}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}