import { useState } from "react";

const DEPT_BADGE = {
  Engineering: "bg-blue-100 text-blue-700",
  Signal: "bg-purple-100 text-purple-700",
  Traction: "bg-orange-100 text-orange-700",
};

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function GanttChart({ weeklySchedule }) {
  const [activeDay, setActiveDay] = useState(0);

  if (!weeklySchedule || weeklySchedule.days.length === 0) {
    return <p className="text-gray-500">No schedule data available.</p>;
  }

  const days = weeklySchedule.days;
  const currentDay = days[activeDay];
  const sortedBlocks = [...currentDay.blocks].sort(
    (a, b) => new Date(a.start_time) - new Date(b.start_time)
  );

  return (
    <div className="bg-white rounded-xl shadow p-5">
      <h2 className="text-lg font-bold text-gray-800 mb-3">Weekly Block Schedule</h2>

      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        {days.map((day, i) => (
          <button
            key={day.date}
            onClick={() => setActiveDay(i)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap ${
              i === activeDay ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {day.date} ({day.blocks.length})
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-200">
              <th className="py-2 pr-3">Section</th>
              <th className="py-2 pr-3">Time</th>
              <th className="py-2 pr-3">Department(s)</th>
              <th className="py-2 pr-3">Task(s)</th>
              <th className="py-2 pr-3">Type</th>
            </tr>
          </thead>
          <tbody>
            {sortedBlocks.map((b) => (
              <tr
                key={b.block_id}
                className={`border-b border-gray-100 ${b.merged ? "bg-emerald-50" : ""}`}
              >
                <td className="py-2 pr-3 font-semibold text-gray-700">{b.section_id}</td>
                <td className="py-2 pr-3 text-gray-600 whitespace-nowrap">
                  {formatTime(b.start_time)} – {formatTime(b.end_time)}
                </td>
                <td className="py-2 pr-3">
                  <div className="flex flex-wrap gap-1">
                    {b.departments_involved.map((d) => (
                      <span key={d} className={`text-xs px-2 py-0.5 rounded-full ${DEPT_BADGE[d] || "bg-gray-100 text-gray-700"}`}>
                        {d}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="py-2 pr-3 text-gray-700">{b.tasks_included.join(", ")}</td>
                <td className="py-2 pr-3">
                  {b.merged ? (
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-200 text-emerald-800">
                      Merged · {b.merge_mode}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-400">Solo</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}