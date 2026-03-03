import { Calendar, Edit3, ExternalLink } from "lucide-react";
import { Link } from "react-router";
import { useLocation } from "react-router";
import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

interface DailySummary {
  id: string;
  date: string;
  displayDate: string;
  keyLearnings: string[];
  reviewAreas: string[];
  sessionCount: number;
  messageCount: number;
}

interface TimelineApiItem {
  id: string;
  date: string;
  display_date: string;
  key_learnings: string[];
  review_areas: string[];
  session_count: number;
  message_count: number;
}

interface TimelineApiResponse {
  task_id: string;
  timeline: TimelineApiItem[];
}

export function SummaryPanel() {
  const location = useLocation();
  const taskMatch = location.pathname.match(/^\/task\/(\w+)/);
  const currentTaskId = taskMatch ? `task_${taskMatch[1]}` : "task_default";
  const [dailySummaries, setDailySummaries] = useState<DailySummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadTimeline = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/history/tasks/${currentTaskId}/timeline`);
        if (!response.ok) {
          throw new Error(`读取时间线失败（${response.status}）`);
        }
        const data: TimelineApiResponse = await response.json();
        if (!cancelled) {
          setDailySummaries(
            (data.timeline || []).map((item) => ({
              id: item.id,
              date: item.date,
              displayDate: item.display_date,
              keyLearnings: item.key_learnings || [],
              reviewAreas: item.review_areas || [],
              sessionCount: item.session_count || 0,
              messageCount: item.message_count || 0,
            }))
          );
        }
      } catch {
        if (!cancelled) {
          setDailySummaries([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadTimeline();
    return () => {
      cancelled = true;
    };
  }, [currentTaskId]);

  return (
    <aside className="w-[300px] bg-white border-l border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">学习时间线</h2>
        <p className="text-sm text-gray-600 mt-1">每日学习总结</p>
      </div>

      {/* Timeline Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && (
          <div className="text-sm text-gray-500 px-2 pb-3">时间线加载中...</div>
        )}

        {!isLoading && dailySummaries.length === 0 && (
          <div className="text-sm text-gray-500 px-2 pb-3">暂无该任务的时间线数据</div>
        )}

        <div className="relative">
          {/* Vertical Line */}
          <div className="absolute left-4 top-3 bottom-3 w-px bg-gradient-to-b from-indigo-200 via-indigo-200 to-transparent"></div>

          {/* Summary Cards */}
          <div className="space-y-6">
            {dailySummaries.map((summary, index) => (
              <div key={summary.id} className="relative pl-10">
                {/* Timeline Dot */}
                <div
                  className={`absolute left-0 top-1.5 w-8 h-8 rounded-full flex items-center justify-center ${
                    index === 0
                      ? "bg-indigo-600 shadow-lg shadow-indigo-200"
                      : "bg-indigo-100"
                  }`}
                >
                  <Calendar
                    className={`w-4 h-4 ${
                      index === 0 ? "text-white" : "text-indigo-600"
                    }`}
                  />
                </div>

                {/* Card */}
                <div
                  className={`bg-white rounded-xl border p-4 hover:shadow-md transition-all ${
                    index === 0
                      ? "border-indigo-200 shadow-sm"
                      : "border-gray-200"
                  }`}
                >
                  {/* Date Header */}
                  <div className="flex items-center justify-between mb-3">
                    <h3
                      className={`font-semibold ${
                        index === 0 ? "text-indigo-600" : "text-gray-900"
                      }`}
                    >
                      {summary.displayDate}
                    </h3>
                    {index === 0 && (
                      <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-medium">
                        今天
                      </span>
                    )}
                  </div>

                  <div className="text-xs text-gray-500 mb-3">
                    {summary.sessionCount} 个会话 · {summary.messageCount} 条消息
                  </div>

                  {/* Key Learnings */}
                  <div className="mb-3">
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                      关键学习点
                    </h4>
                    <ul className="space-y-1.5">
                      {summary.keyLearnings.map((learning, idx) => (
                        <li
                          key={idx}
                          className="text-sm text-gray-700 flex items-start gap-2"
                        >
                          <span className="text-indigo-500 mt-1">•</span>
                          <span className="flex-1">{learning}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Review Areas */}
                  {summary.reviewAreas.length > 0 && (
                    <div className="mb-3">
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                        待复习
                      </h4>
                      <ul className="space-y-1.5">
                        {summary.reviewAreas.map((area, idx) => (
                          <li
                            key={idx}
                            className="text-sm text-amber-700 flex items-start gap-2"
                          >
                            <span className="text-amber-500 mt-1">•</span>
                            <span className="flex-1">{area}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* View Full Chat Log */}
                  <div className="flex items-center gap-2 mt-2">
                    <Link
                      to={`/history/${summary.date}?task_id=${currentTaskId}`}
                      className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      <span>查看完整对话记录</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                    <span className="text-gray-300">|</span>
                    <Link
                      to={`/daily-note/${summary.date}?task_id=${currentTaskId}`}
                      className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-700 font-medium"
                    >
                      <Edit3 className="w-3 h-3" />
                      <span>笔记</span>
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}