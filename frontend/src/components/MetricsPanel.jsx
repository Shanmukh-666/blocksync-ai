export default function MetricsPanel({ metrics }) {
  if (!metrics) return null;

  const { throughput, merging_efficiency, safety } = metrics;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {/* Throughput Card */}
      <div className="bg-white rounded-xl shadow p-5 border-l-4 border-blue-500">
        <h3 className="text-sm font-semibold text-gray-500 uppercase mb-2">Throughput</h3>
        <p className="text-3xl font-bold text-gray-800">
          {throughput.ai_scheduled}
          <span className="text-lg text-gray-400"> / {throughput.ai_scheduled + (throughput.additional_tasks_by_ai < 0 ? 0 : 0)}</span>
        </p>
        <p className="text-sm text-gray-500 mt-1">tasks scheduled by BlockSync AI</p>
        <p className="text-sm font-medium text-blue-600 mt-2">
          +{throughput.additional_tasks_by_ai} more than manual process
        </p>
        <p className="text-xs text-gray-400 mt-1">(manual: {throughput.naive_scheduled} tasks)</p>
      </div>

      {/* Merging Efficiency Card */}
      <div className="bg-white rounded-xl shadow p-5 border-l-4 border-emerald-500">
        <h3 className="text-sm font-semibold text-gray-500 uppercase mb-2">Merging Efficiency</h3>
        <p className="text-3xl font-bold text-gray-800">
          {merging_efficiency.downtime_saved_pct}%
        </p>
        <p className="text-sm text-gray-500 mt-1">downtime saved via merging</p>
        <p className="text-sm font-medium text-emerald-600 mt-2">
          {merging_efficiency.total_merges} cross-department merges
        </p>
        <p className="text-xs text-gray-400 mt-1">
          {merging_efficiency.hours_without_merging}h → {merging_efficiency.hours_with_ai_merging}h
        </p>
      </div>

      {/* Safety Card */}
      <div className="bg-white rounded-xl shadow p-5 border-l-4 border-red-500">
        <h3 className="text-sm font-semibold text-gray-500 uppercase mb-2">Safety Guarantee</h3>
        <p className="text-3xl font-bold text-gray-800">
          {safety.severity5_missed_by_ai_count}
          <span className="text-lg text-gray-400"> critical missed</span>
        </p>
        <p className="text-sm text-gray-500 mt-1">by BlockSync AI (R12 guarantee)</p>
        <p className="text-sm font-medium text-red-600 mt-2">
          Manual process missed {safety.severity5_missed_by_naive_count}
        </p>
        <p className="text-xs text-gray-400 mt-1">
          {safety.severity5_missed_by_naive.join(", ") || "none"}
        </p>
      </div>
    </div>
  );
}