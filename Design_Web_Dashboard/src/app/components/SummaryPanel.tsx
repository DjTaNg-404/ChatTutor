import { Calendar, Edit3, ExternalLink } from "lucide-react";
import { Link } from "react-router";
import { useLocation } from "react-router";
import { useEffect, useState, useCallback } from "react";

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

interface TaskPlan {
  taskTitle?: string;
  startDate?: string;
  totalDays?: number;
  totalHours?: number;
  progress?: number;
  overallSummary?: string;
  coreKnowledge?: string[];
  masteryLevel?: { topic: string; level: number }[];
  milestones?: { date: string; achievement: string }[];
  plan?: string[] | string;
  planChecklist?: { [key: string]: boolean };
}

export function SummaryPanel() {
  const location = useLocation();
  const taskMatch = location.pathname.match(/^\/task\/(.+)$/);
  const rawTaskId = taskMatch ? taskMatch[1] : "";
  const currentTaskId = rawTaskId
    ? rawTaskId.startsWith("task_")
      ? rawTaskId
      : `task_${rawTaskId}`
    : "task_default";
  const [dailySummaries, setDailySummaries] = useState<DailySummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  const [isPlanLoading, setIsPlanLoading] = useState(false);
  const [planChecklist, setPlanChecklist] = useState<{ [key: string]: boolean }>({});

  const normalizePlanSteps = useCallback((plan: TaskPlan | null): string[] => {
    if (!plan) return [];
    const raw = (plan as { plan?: unknown }).plan;
    if (Array.isArray(raw)) {
      const steps = raw.map((item) => String(item)).filter((item) => item.trim());
      if (steps.length > 0) {
        return steps;
      }
    }
    if (typeof raw === "string") {
      const steps = raw
        .split(/\r?\n|[；;]+/)
        .map((item) => item.trim())
        .filter(Boolean);
      if (steps.length > 0) {
        return steps;
      }
    }
    if (plan.overallSummary) {
      return [plan.overallSummary];
    }
    return [];
  }, []);

  const planSteps = normalizePlanSteps(taskPlan);

  // 找到第一个未完成的项目索引
  const firstUncheckedIndex = planSteps.findIndex(
    (_, idx) => !planChecklist[String(idx)]
  );

  // 保存学习计划打勾状态
  const handleSavePlanChecklist = useCallback(async (checklist: { [key: string]: boolean }) => {
    try {
      console.log("保存打勾状态:", {
        task_id: currentTaskId,
        checklist,
      });

      const response = await fetch(`${API_BASE_URL}/notes/task/plan-checklist`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: currentTaskId,
          checklist,
        }),
      });

      console.log("保存响应状态:", response.status);

      if (!response.ok) {
        throw new Error(`保存进度失败（${response.status}）`);
      }
      // 触发任务计划更新事件，通知其他组件同步状态
      window.dispatchEvent(new Event("task-plan-updated"));
    } catch (error) {
      console.error("保存学习计划进度失败:", error);
    }
  }, [currentTaskId]);

  // 处理单个项目的打勾切换
  const handleTogglePlanItem = useCallback((index: number) => {
    const key = String(index);
    const newChecklist = { ...planChecklist, [key]: !planChecklist[key] };
    setPlanChecklist(newChecklist);
    void handleSavePlanChecklist(newChecklist);
  }, [planChecklist, handleSavePlanChecklist]);

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

    const loadPlan = async () => {
      setIsPlanLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/notes/task?task_id=${currentTaskId}`);
        if (!response.ok) {
          throw new Error("failed");
        }
        const data = await response.json();
        const hasPlan =
          Boolean(data.taskTitle) ||
          Boolean(data.overallSummary) ||
          Boolean(data.coreKnowledge && data.coreKnowledge.length) ||
          Boolean(data.masteryLevel && data.masteryLevel.length) ||
          Boolean(data.milestones && data.milestones.length) ||
          Boolean(data.plan && data.plan.length);
        if (!cancelled) {
          setTaskPlan(hasPlan ? data : null);
          setPlanChecklist(data.planChecklist || {});
        }
      } catch {
        if (!cancelled) {
          setTaskPlan(null);
          setPlanChecklist({});
        }
      } finally {
        if (!cancelled) {
          setIsPlanLoading(false);
        }
      }
    };

    const handlePlanUpdated = () => {
      void loadPlan();
    };

    const handleTimelineUpdated = () => {
      void loadTimeline();
    };

    void loadTimeline();
    void loadPlan();
    window.addEventListener("task-plan-updated", handlePlanUpdated);
    window.addEventListener("timeline-updated", handleTimelineUpdated);
    return () => {
      cancelled = true;
      window.removeEventListener("task-plan-updated", handlePlanUpdated);
      window.removeEventListener("timeline-updated", handleTimelineUpdated);
    };
  }, [currentTaskId]);

  return (
    <aside className="w-[300px] bg-white border-l border-gray-200 flex flex-col h-full">
      <section className="flex-1 min-h-0 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">学习时间线</h2>
          <p className="text-sm text-gray-600 mt-1">每日学习总结</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading && (
            <div className="text-sm text-gray-500 px-2 pb-3">时间线加载中...</div>
          )}

          {!isLoading && dailySummaries.length === 0 && (
            <div className="text-sm text-gray-500 px-2 pb-3">暂无该任务的时间线数据</div>
          )}

          <div className="relative">
            <div className="absolute left-4 top-3 bottom-3 w-px bg-gradient-to-b from-indigo-200 via-indigo-200 to-transparent"></div>

            <div className="space-y-6">
              {dailySummaries.map((summary, index) => (
                <div key={summary.id} className="relative pl-10">
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

                  <div
                    className={`bg-white rounded-xl border p-4 hover:shadow-md transition-all ${
                      index === 0
                        ? "border-indigo-200 shadow-sm"
                        : "border-gray-200"
                    }`}
                  >
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
      </section>

      <section className="flex-1 min-h-0 flex flex-col border-t border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">详细学习计划</h3>
          <p className="text-sm text-gray-600 mt-1">当前学习计划</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {isPlanLoading && (
            <div className="text-xs text-gray-500">计划加载中...</div>
          )}
          {!isPlanLoading && (!taskPlan || planSteps.length === 0) && (
            <div className="flex flex-col items-center justify-center gap-3 text-center text-xs text-gray-500 py-8">
              <div>暂无详细学习计划</div>
              <button
                onClick={() =>
                  window.dispatchEvent(
                    new CustomEvent("request-plan", {
                      detail: { taskId: currentTaskId },
                    })
                  )
                }
                className="px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                生成一个计划
              </button>
            </div>
          )}
          {!isPlanLoading && taskPlan && planSteps.length > 0 && (
            <div className="space-y-2">
              {planSteps.map((step, idx) => {
                const key = String(idx);
                const isChecked = planChecklist[key];
                const isFirstIncomplete = idx === firstUncheckedIndex;
                return (
                  <div
                    key={idx}
                    className={`flex items-start gap-2 text-sm rounded-lg p-2 transition-all ${
                      isChecked
                        ? "bg-gray-100"
                        : isFirstIncomplete
                        ? "bg-white border border-indigo-200"
                        : "bg-white"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked || false}
                      onChange={() => handleTogglePlanItem(idx)}
                      className="mt-0.5 w-4 h-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500 cursor-pointer flex-shrink-0"
                    />
                    <span
                      className={`flex-1 ${
                        isChecked
                          ? "line-through text-gray-400"
                          : isFirstIncomplete
                          ? "font-bold text-gray-900"
                          : "text-gray-700"
                      }`}
                    >
                      {step}
                    </span>
                    {isFirstIncomplete && !isChecked && (
                      <span className="text-xs text-indigo-600 font-medium px-1.5 py-0.5 bg-indigo-100 rounded-full flex-shrink-0">
                        当前
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </aside>
  );
}
