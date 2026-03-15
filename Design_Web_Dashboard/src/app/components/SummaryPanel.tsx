import { ChevronLeft, ChevronRight } from "lucide-react";
import { Link } from "react-router";
import { useLocation } from "react-router";
import { useEffect, useState, useCallback, useMemo, useRef } from "react";

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
  const [currentMonth, setCurrentMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [hasDailyNote, setHasDailyNote] = useState<boolean | null>(null);
  const [isCheckingNote, setIsCheckingNote] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);

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
        .split(/\r?\n|[\\uFF0C,]+/)
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

  const timelineCountMap = useMemo(() => {
    const map = new Map<string, number>();
    dailySummaries.forEach((item) => {
      map.set(item.date, item.messageCount || 0);
    });
    return map;
  }, [dailySummaries]);

  const formatDateKey = (year: number, monthIndex: number, day: number) => {
    const month = `${monthIndex + 1}`.padStart(2, "0");
    const date = `${day}`.padStart(2, "0");
    return `${year}-${month}-${date}`;
  };

  const monthLabel = useMemo(() => {
    return currentMonth.toLocaleString("zh-CN", {
      year: "numeric",
      month: "long",
    });
  }, [currentMonth]);

  const calendarCells = useMemo(() => {
    const year = currentMonth.getFullYear();
    const monthIndex = currentMonth.getMonth();
    const firstDay = new Date(year, monthIndex, 1);
    const lastDay = new Date(year, monthIndex + 1, 0);
    const startWeekday = firstDay.getDay();
    const daysInMonth = lastDay.getDate();
    const totalCells = Math.ceil((startWeekday + daysInMonth) / 7) * 7;
    return Array.from({ length: totalCells }, (_, idx) => {
      const day = idx - startWeekday + 1;
      if (day < 1 || day > daysInMonth) return null;
      const dateKey = formatDateKey(year, monthIndex, day);
      const count = timelineCountMap.get(dateKey) || 0;
      return { day, dateKey, count };
    });
  }, [currentMonth, timelineCountMap]);

  const getIntensityClass = (count: number) => {
    if (count <= 0) return "bg-gray-100";
    if (count <= 2) return "bg-emerald-100";
    if (count <= 5) return "bg-emerald-200";
    if (count <= 10) return "bg-emerald-300";
    return "bg-emerald-500";
  };

  const handleMonthChange = (delta: number) => {
    setCurrentMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
    setSelectedDate(null);
    setHasDailyNote(null);
  };

  const checkDailyNote = async (dateKey: string) => {
    setIsCheckingNote(true);
    setHasDailyNote(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/notes/daily?task_id=${encodeURIComponent(currentTaskId)}&date=${encodeURIComponent(dateKey)}`
      );
      setHasDailyNote(response.ok);
    } catch {
      setHasDailyNote(false);
    } finally {
      setIsCheckingNote(false);
    }
  };

  const showToast = (message: string) => {
    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current);
    }
    setToastMessage(message);
    toastTimerRef.current = window.setTimeout(() => {
      setToastMessage(null);
      toastTimerRef.current = null;
    }, 2000);
  };

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

          <div className="relative bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
            {toastMessage && (
              <div className="absolute right-3 top-3 z-10 rounded-lg bg-gray-900/90 px-3 py-1.5 text-[11px] text-white shadow">
                {toastMessage}
              </div>
            )}
            <div className="flex items-center justify-between mb-4">
              <button
                type="button"
                onClick={() => handleMonthChange(-1)}
                className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <div className="text-sm font-semibold text-gray-700">{monthLabel}</div>
              <button
                type="button"
                onClick={() => handleMonthChange(1)}
                className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-7 gap-1 text-[10px] text-gray-400 mb-2">
              {["\u65e5", "\u4e00", "\u4e8c", "\u4e09", "\u56db", "\u4e94", "\u516d"].map((label) => (
                <div key={label} className="text-center">{label}</div>
              ))}
            </div>

            <div className="grid grid-cols-7 gap-1">
              {calendarCells.map((cell, idx) => {
                if (!cell) {
                  return <div key={`empty-${idx}`} className="h-6" />;
                }
                const isSelected = selectedDate === cell.dateKey;
                return (
                  <div key={cell.dateKey} className="relative group flex justify-center">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedDate(cell.dateKey);
                        void checkDailyNote(cell.dateKey);
                      }}
                      className={`h-6 w-6 rounded-sm ${getIntensityClass(cell.count)} text-[9px] font-medium text-gray-700 flex items-center justify-center ${
                        isSelected ? "ring-2 ring-emerald-500" : "hover:ring-2 hover:ring-emerald-300"
                      } transition`}
                      aria-label={`${cell.dateKey} 消息数 ${cell.count}`}
                    >
                      {cell.day}
                    </button>
                  </div>
                );
              })}
            </div>

            {selectedDate && (
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <Link
                  to={`/history/${selectedDate}?task_id=${currentTaskId}`}
                  onClick={(event) => {
                    const count = timelineCountMap.get(selectedDate) || 0;
                    if (count <= 0) {
                      event.preventDefault();
                      showToast("当日暂无对话记录");
                    }
                  }}
                  className="px-4 py-2 text-xs font-medium bg-gray-800 text-white rounded-full hover:bg-gray-700 transition"
                >
                  跳转记录
                </Link>
                {hasDailyNote && (
                  <Link
                    to={`/daily-note/${selectedDate}?task_id=${currentTaskId}`}
                    className="px-4 py-2 text-xs font-medium bg-indigo-600 text-white rounded-full hover:bg-indigo-700 transition"
                  >
                    查看当日学习笔记
                  </Link>
                )}
              </div>
            )}
            {selectedDate && isCheckingNote && (
              <div className="mt-3 text-center text-xs text-gray-400">正在检查当日笔记...</div>
            )}
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
