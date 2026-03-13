import { useState } from "react";
import { useNavigate } from "react-router";
import {
  ArrowLeft,
  Sparkles,
  ClipboardCheck,
  Target,
  BookOpen,
  CheckCircle2,
  Loader2,
  Lightbulb,
  Palette,
} from "lucide-react";

const COMMON_ICONS = [
  { icon: "📚", label: "书本" },
  { icon: "🎯", label: "目标" },
  { icon: "💻", label: "电脑" },
  { icon: "📊", label: "图表" },
  { icon: "🔬", label: "科学" },
  { icon: "📝", label: "笔记" },
  { icon: "🎓", label: "学位" },
  { icon: "📖", label: "开放书" },
  { icon: "🧮", label: "算盘" },
  { icon: "🔢", label: "数字" },
  { icon: "🔤", label: "字母" },
  { icon: "📚", label: "书籍堆" },
  { icon: "🌳", label: "树" },
  { icon: "🗣️", label: "说话" },
  { icon: "⚛️", label: "原子" },
  { icon: "🐍", label: "蛇" },
  { icon: "💾", label: "磁盘" },
  { icon: "⭐", label: "星星" },
  { icon: "🚀", label: "火箭" },
  { icon: "💡", label: "灯泡" },
  { icon: "🏆", label: "奖杯" },
  { icon: "📈", label: "增长" },
  { icon: "🎨", label: "艺术" },
  { icon: "🎵", label: "音乐" },
  { icon: "🧠", label: "大脑" },
  { icon: "⚡", label: "闪电" },
  { icon: "🔥", label: "火焰" },
  { icon: "💪", label: "力量" },
  { icon: "🌟", label: "闪亮" },
  { icon: "✨", label: "火花" },
];

interface TaskPlan {
  task_id?: string;
  taskTitle?: string;
  taskIcon?: string;
  startDate?: string;
  totalDays?: number;
  totalHours?: number;
  progress?: number;
  overallSummary?: string;
  coreKnowledge?: string[];
  masteryLevel?: { topic: string; level: number }[];
  milestones?: { date: string; achievement: string }[];
  plan?: string[] | string;
  _plan_sig?: string;
}

function makeTaskId() {
  const stamp = Date.now().toString(36);
  return `task_${stamp}`;
}

function formatPlanAsGoal(plan: TaskPlan): string {
  const lines: string[] = [];
  if (plan.overallSummary) {
    lines.push(plan.overallSummary.trim());
  }

  const rawSteps = (plan as { plan?: unknown }).plan;
  const steps = Array.isArray(rawSteps)
    ? rawSteps.map((item) => String(item)).filter((item) => item.trim())
    : typeof rawSteps === "string"
      ? rawSteps
          .split(/\r?\n|[；;]+/)
          .map((item) => item.trim())
          .filter(Boolean)
      : [];

  if (steps.length > 0) {
    lines.push("");
    lines.push("计划步骤：");
    steps.forEach((step, idx) => {
      lines.push(`${idx + 1}. ${step}`);
    });
  }

  return lines.join("\n").trim();
}

async function saveTaskToIndex(task: { id: string; title: string; icon: string }) {
  await fetch(`${API_BASE_URL}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_id: task.id,
      title: task.title,
      icon: task.icon,
      status: "active",
    }),
  });
}

function IconPicker({
  selectedIcon,
  onSelect,
}: {
  selectedIcon: string;
  onSelect: (icon: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl hover:bg-gray-100 transition-colors"
      >
        <Palette className="w-4 h-4 text-gray-500" />
        <span className="text-sm text-gray-700">选择图标</span>
        <span className="text-lg">{selectedIcon}</span>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute top-full left-0 mt-2 z-20 w-72 bg-white border border-gray-200 rounded-xl shadow-lg p-3">
            <div className="grid grid-cols-6 gap-2 max-h-64 overflow-y-auto">
              {COMMON_ICONS.map((item) => (
                <button
                  key={item.icon}
                  type="button"
                  onClick={() => {
                    onSelect(item.icon);
                    setIsOpen(false);
                  }}
                  className={`w-10 h-10 flex items-center justify-center text-lg rounded-lg transition-colors ${
                    selectedIcon === item.icon
                      ? "bg-indigo-100 ring-2 ring-indigo-500"
                      : "hover:bg-gray-100"
                  }`}
                  title={item.label}
                >
                  {item.icon}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export function NewTaskPage() {
  const navigate = useNavigate();
  const [taskTitle, setTaskTitle] = useState("");
  const [taskGoal, setTaskGoal] = useState("");
  const [taskIcon, setTaskIcon] = useState("⭐");
  const [taskId] = useState(makeTaskId);
  const [plan, setPlan] = useState<TaskPlan | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const canGenerate = taskTitle.trim() && taskGoal.trim() && !isGenerating;
  const canConfirm = taskTitle.trim() && taskGoal.trim() && !isConfirming;

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setIsGenerating(true);
    setHint(null);

    try {
      const response = await fetch(`${API_BASE_URL}/agent/task-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          user_goal: taskGoal,
          constraints: "",
          current_level: "",
        }),
      });

      if (!response.ok) {
        throw new Error(`生成计划失败（${response.status}）`);
      }

      const data = (await response.json()) as TaskPlan;
      const merged = {
        ...data,
        taskTitle: data.taskTitle || taskTitle,
      };
      setPlan(merged);
      const formattedGoal = formatPlanAsGoal(merged);
      if (formattedGoal) {
        setTaskGoal(formattedGoal);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "生成计划失败";
      setHint(message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleConfirm = async () => {
    if (!canConfirm) return;
    setIsConfirming(true);
    setHint(null);

    try {
      const planPayload: TaskPlan = plan || {
        taskTitle: taskTitle || "学习任务",
        overallSummary: taskGoal,
        coreKnowledge: [],
        plan: [],
      };

      const response = await fetch(`${API_BASE_URL}/agent/task-plan/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          plan: {
            ...planPayload,
            taskTitle: taskTitle || planPayload.taskTitle,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`确认失败（${response.status}）`);
      }

      const icon = taskIcon || plan?.taskIcon || "✨";
      const title = taskTitle || plan?.taskTitle || "学习任务";
      await saveTaskToIndex({ id: taskId, title, icon });
      window.dispatchEvent(new Event("tasks-updated"));
      window.dispatchEvent(new Event("task-plan-updated"));
      navigate(`/task/${taskId}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "确认失败";
      setHint(message);
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-3 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm font-medium">返回</span>
          </button>

          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 rounded-xl">
              <BookOpen className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-gray-100 text-[11px] text-gray-500 uppercase tracking-wide">
                Preview
              </span>
              <h1 className="text-2xl font-semibold text-gray-900 mt-1">创建新的学习任务</h1>
              <p className="text-sm text-gray-600 mt-1">
                设定目标，让 AI 为你规划学习路径
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-indigo-600" />
              <h2 className="text-base font-semibold text-gray-900">任务名称</h2>
              <span className="text-rose-500 text-sm font-medium">*</span>
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <input
                  value={taskTitle}
                  onChange={(event) => setTaskTitle(event.target.value)}
                  placeholder="输入任务名称（简洁描述你的学习主题）"
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <IconPicker selectedIcon={taskIcon} onSelect={setTaskIcon} />
            </div>
          </section>

          <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <ClipboardCheck className="w-4 h-4 text-indigo-600" />
              <h2 className="text-base font-semibold text-gray-900">学习目标</h2>
              <span className="text-rose-500 text-sm font-medium">*</span>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              详细描述你想达到的学习目标，包括具体的知识点、技能水平、应用场景等
            </p>
            <textarea
              value={taskGoal}
              onChange={(event) => setTaskGoal(event.target.value)}
              placeholder="请描述你的学习目标、希望达到的能力水平，以及计划应用的场景。"
              rows={7}
              className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </section>

          <div className="flex flex-col items-center gap-3">
            <button
              onClick={() => void handleGenerate()}
              disabled={!canGenerate}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-full hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">AI 生成学习计划</span>
            </button>
            {hint && <span className="text-sm text-rose-600">{hint}</span>}
            <button
              onClick={() => void handleConfirm()}
              disabled={!canConfirm}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {isConfirming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">确认使用这个学习计划</span>
            </button>
            {!plan && (
              <span className="text-xs text-gray-500">先生成计划后再确认</span>
            )}
          </div>

          <section className="bg-blue-50 rounded-2xl border border-blue-100 p-4">
            <div className="flex items-center gap-2 text-blue-700">
              <Lightbulb className="w-4 h-4" />
              <span className="text-sm font-semibold">小贴士</span>
            </div>
            <p className="text-sm text-blue-700 mt-2">
              写得越具体，AI 生成的学习计划越贴合你的真实目标。
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
