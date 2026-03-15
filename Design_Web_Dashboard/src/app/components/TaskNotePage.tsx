import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router";
import { ArrowLeft, BookOpen, Calendar, TrendingUp, Target, Clock, Edit3, Eye, Pencil, Network } from "lucide-react";
import { MarkdownPreview } from "./MarkdownPreview";
import { KGViewerModal } from "./KGViewerModal";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

interface TaskNoteApiResponse {
  task_id: string;
  content?: string;
  userNotes?: string;
  taskTitle?: string;
  taskIcon?: string;
  startDate?: string;
  totalDays?: number;
  totalHours?: number;
  progress?: number;
  overallSummary?: string;
  coreKnowledge?: string[];
  masteryLevel?: {
    topic: string;
    level: number;
  }[];
  milestones?: {
    date: string;
    achievement: string;
  }[];
  plan?: string[] | string;
  planChecklist?: { [key: string]: boolean }; // 学习计划打勾状态
  updated_at?: string;
}

interface TaskNote {
  taskId: string;
  taskTitle: string;
  taskIcon: string;
  startDate: string;
  totalDays: number;
  totalHours: number;
  progress: number;
  overallSummary: string;
  coreKnowledge: string[];
  masteryLevel: {
    topic: string;
    level: number; // 0-100
  }[];
  milestones: {
    date: string;
    achievement: string;
  }[];
  plan: string[] | string;
  userNotes: string;
  planChecklist?: { [key: string]: boolean }; // 学习计划打勾状态
}

// 模拟任务笔记数据
const taskNotesData: { [key: string]: TaskNote } = {
  "1": {
    taskId: "1",
    taskTitle: "掌握随机森林算法",
    taskIcon: "🌳",
    startDate: "2026-02-25",
    totalDays: 6,
    totalHours: 8.5,
    progress: 75,
    overallSummary:
      "本任务旨在全面掌握随机森林算法的理论基础和实践应用。通过系统学习，已经理解了集成学习的核心思想、特征重要性评估方法、超参数调优技巧，以及与其他算法的对比分析。目前已完成理论学习阶段，正在进入实践应用阶段。",
    coreKnowledge: [
      "集成学习原理（Ensemble Learning）",
      "Bootstrap 采样与特征随机性",
      "特征重要性计算（Gini Importance）",
      "超参数调优（n_estimators, max_depth, min_samples_split）",
      "随机森林 vs XGBoost vs 决策树对比",
      "过拟合控制与交叉验证",
    ],
    masteryLevel: [
      { topic: "理论基础", level: 85 },
      { topic: "特征重要性", level: 80 },
      { topic: "超参数调优", level: 70 },
      { topic: "实践应用", level: 50 },
      { topic: "优化技巧", level: 45 },
    ],
    milestones: [
      { date: "2026-02-25", achievement: "开始学习随机森林，了解基本概念" },
      { date: "2026-02-28", achievement: "完成决策树基础复习" },
      { date: "2026-03-01", achievement: "深入理解信息增益与基尼系数" },
      { date: "2026-03-02", achievement: "掌握特征重要性和超参数调优" },
    ],
    plan: [
      "使用 Kaggle 泰坦尼克数据集进行实践练习",
      "对比随机森林与 XGBoost 在真实数据上的表现",
      "学习特征工程技巧并应用到模型中",
      "研究随机森林在不平衡数据上的处理方法",
      "尝试调优复杂场景下的超参数",
    ],
    userNotes:
      "## 个人心得\n\n随机森林是一个非常实用的算法，理解起来相对简单，但要用好需要大量实践。\n\n## 重点难点\n\n1. 特征重要性的计算原理需要反复理解\n2. 超参数之间的相互影响需要实践总结\n3. 如何避免过拟合是关键\n\n## 参考资源\n\n- Scikit-learn 官方文档\n- 《统计学习方法》李航\n- Kaggle 相关竞赛案例\n\n## 实践项目计划\n\n- [ ] 泰坦尼克生存预测\n- [ ] 房价预测项目\n- [ ] 信用卡欺诈检测",
  },
  "2": {
    taskId: "2",
    taskTitle: "雅思口语备考",
    taskIcon: "🗣️",
    startDate: "2026-02-20",
    totalDays: 11,
    totalHours: 15.5,
    progress: 60,
    overallSummary: "系统性地准备雅思口语考试，重点提升流利度和词汇丰富度。",
    coreKnowledge: [
      "Part 1 常见话题应对策略",
      "Part 2 长篇陈述结构",
      "Part 3 深度讨论技巧",
    ],
    masteryLevel: [
      { topic: "发音", level: 75 },
      { topic: "流利度", level: 65 },
      { topic: "词汇", level: 70 },
      { topic: "语法", level: 80 },
    ],
    milestones: [
      { date: "2026-02-20", achievement: "开始口语备考计划" },
      { date: "2026-02-25", achievement: "完成 Part 1 基础话题练习" },
    ],
    plan: [
      "每天练习 Part 2 话题",
      "积累高分词汇和表达",
      "进行模拟考试",
    ],
    userNotes: "需要多练习，提高自信心。",
  },
};

function mergeTaskNote(
  fallback: TaskNote | null,
  api: TaskNoteApiResponse | null,
  taskId: string | undefined
): TaskNote | null {
  if (!fallback && !api) {
    return null;
  }

  return {
    taskId: api?.task_id || fallback?.taskId || taskId || "task_default",
    taskTitle: api?.taskTitle || fallback?.taskTitle || "Task Plan",
    taskIcon: api?.taskIcon || fallback?.taskIcon || "*",
    startDate: api?.startDate || fallback?.startDate || "",
    totalDays: api?.totalDays ?? fallback?.totalDays ?? 0,
    totalHours: api?.totalHours ?? fallback?.totalHours ?? 0,
    progress: api?.progress ?? fallback?.progress ?? 0,
    overallSummary: api?.overallSummary || fallback?.overallSummary || "",
    coreKnowledge: api?.coreKnowledge || fallback?.coreKnowledge || [],
    masteryLevel: api?.masteryLevel || fallback?.masteryLevel || [],
    milestones: api?.milestones || fallback?.milestones || [],
    plan: api?.plan || fallback?.plan || [],
    userNotes: api?.userNotes || api?.content || fallback?.userNotes || "",
    planChecklist: api?.planChecklist || fallback?.planChecklist || {},
  };
}

export function TaskNotePage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();

  const noteData = taskId ? taskNotesData[taskId] : null;
  const resolvedTaskId = taskId
    ? taskId.startsWith("task_")
      ? taskId
      : `task_${taskId}`
    : "task_default";
  const [taskNote, setTaskNote] = useState<TaskNote | null>(
    mergeTaskNote(noteData, null, taskId)
  );
  const [userNotes, setUserNotes] = useState(taskNote?.userNotes || "");
  const [isPreviewMode, setIsPreviewMode] = useState(false);

  const normalizePlanSteps = (steps?: TaskNote["plan"]): string[] => {
    if (!steps) return [];
    if (Array.isArray(steps)) {
      return steps.map((item) => String(item)).filter((item) => item.trim());
    }
    if (typeof steps === "string") {
      return steps
        .split(/\r?\n|[；;]+/)
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return [];
  };
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveHint, setSaveHint] = useState<string | null>(null);
  const [planChecklist, setPlanChecklist] = useState<{ [key: string]: boolean }>({});
  const [isKgViewerOpen, setIsKgViewerOpen] = useState(false);

  // 找到第一个未完成的项目索引
  const firstUncheckedIndex = normalizePlanSteps(taskNote?.plan).findIndex(
    (_, idx) => !planChecklist[String(idx)]
  );

  const loadTaskNote = useCallback(async () => {
    let cancelled = false;
    setIsLoading(true);
    setSaveHint(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/notes/task?task_id=${encodeURIComponent(resolvedTaskId)}`
      );
      if (!response.ok) {
        throw new Error(`加载任务笔记失败（${response.status}）`);
      }
      const data: TaskNoteApiResponse = await response.json();
      if (!cancelled) {
        const merged = mergeTaskNote(noteData, data, taskId);
        setTaskNote(merged);
        setUserNotes(merged?.userNotes || "");
        setPlanChecklist(merged?.planChecklist || {});

      }
    } catch (error) {
      if (!cancelled) {
        const message = error instanceof Error ? error.message : "加载任务笔记失败";
        setSaveHint(message);
        const merged = mergeTaskNote(noteData, null, taskId);
        setTaskNote(merged);
        setUserNotes(merged?.userNotes || "");
        setPlanChecklist(merged?.planChecklist || {});
      }
    } finally {
      if (!cancelled) {
        setIsLoading(false);
      }
    }
  }, [resolvedTaskId, taskId, noteData]);

  // 保存学习计划打勾状态
  const handleSavePlanChecklist = async (checklist: { [key: string]: boolean }) => {
    try {
      console.log("保存打勾状态:", {
        task_id: resolvedTaskId,
        checklist,
      });

      const response = await fetch(`${API_BASE_URL}/notes/task/plan-checklist`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: resolvedTaskId,
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
  };

  // 处理单个项目的打勾切换
  const handleTogglePlanItem = (index: number) => {
    const key = String(index);
    const newChecklist = { ...planChecklist, [key]: !planChecklist[key] };
    setPlanChecklist(newChecklist);
    void handleSavePlanChecklist(newChecklist);
  };

  useEffect(() => {
    void loadTaskNote();
    window.addEventListener("task-plan-updated", loadTaskNote);
    return () => {
      window.removeEventListener("task-plan-updated", loadTaskNote);
    };
  }, [loadTaskNote]);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveHint(null);
    try {
      const response = await fetch(`${API_BASE_URL}/notes/task`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: resolvedTaskId,
          content: userNotes,
        }),
      });

      if (!response.ok) {
        throw new Error(`保存失败（${response.status}）`);
      }
      setSaveHint("已保存");
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存失败";
      setSaveHint(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (!taskNote) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <BookOpen className="w-8 h-8 text-gray-400" />
          </div>
          <p className="text-gray-500">暂无此任务的笔记</p>
          <button
            onClick={() => navigate(-1)}
            className="mt-4 text-indigo-600 hover:text-indigo-700 text-sm font-medium"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-3 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm font-medium">返回</span>
          </button>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-4xl">{taskNote.taskIcon}</span>
              <div>
                <h1 className="text-2xl font-semibold text-gray-900">
                  {taskNote.taskTitle}
                </h1>
                <p className="text-sm text-gray-600 mt-0.5">任务总览与学习笔记</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsKgViewerOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
              >
                <Network className="w-4 h-4" />
                <span className="text-sm font-medium">查看知识图谱</span>
              </button>

              <button
                onClick={() => void handleSave()}
                disabled={isSaving || isLoading}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                <Edit3 className="w-4 h-4" />
                <span className="text-sm font-medium">{isSaving ? "保存中..." : "保存笔记"}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Progress Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-100 rounded-lg">
                  <Calendar className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">学习天数</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {taskNote.totalDays} 天
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <Clock className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">累计时长</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {taskNote.totalHours} 小时
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <TrendingUp className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">完成进度</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {taskNote.progress}%
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <Target className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">里程碑</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {taskNote.milestones.length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Overall Summary */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">任务概述</h2>
            <p className="text-gray-700 leading-relaxed">{taskNote.overallSummary}</p>
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Core Knowledge */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                核心知识点
              </h2>
              <ul className="space-y-2">
                {taskNote.coreKnowledge.map((knowledge, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-sm text-gray-700"
                  >
                    <span className="text-indigo-600 mt-1">•</span>
                    <span className="flex-1">{knowledge}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Mastery Level */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                掌握程度
              </h2>
              <div className="space-y-3">
                {taskNote.masteryLevel.map((item, idx) => (
                  <div key={idx}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-700 font-medium">{item.topic}</span>
                      <span className="text-indigo-600 font-semibold">
                        {item.level}%
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all"
                        style={{ width: `${item.level}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Milestones Timeline */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">学习里程碑</h2>
            <div className="space-y-3">
              {taskNote.milestones.map((milestone, idx) => (
                <div key={idx} className="flex items-start gap-3">
                  <div className="p-1.5 bg-indigo-100 rounded-full mt-0.5">
                    <div className="w-2 h-2 bg-indigo-600 rounded-full" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">
                      {milestone.achievement}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">{milestone.date}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Next Steps */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">详细学习计划</h2>
            <ul className="space-y-2">
              {normalizePlanSteps(taskNote?.plan).map((step, idx) => {
                const key = String(idx);
                const isChecked = planChecklist[key];
                const isFirstIncomplete = idx === firstUncheckedIndex;
                return (
                  <li
                    key={idx}
                    className={`flex items-start gap-3 text-sm rounded-lg p-3 transition-all ${
                      isChecked
                        ? "bg-gray-100"
                        : isFirstIncomplete
                        ? "bg-white border-2 border-indigo-300 shadow-md"
                        : "bg-white"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked || false}
                      onChange={() => handleTogglePlanItem(idx)}
                      className="mt-1 w-4 h-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500 cursor-pointer"
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
                      <span className="text-xs text-indigo-600 font-medium px-2 py-0.5 bg-indigo-100 rounded-full">
                        当前进度
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
            {normalizePlanSteps(taskNote?.plan).length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">暂无学习计划</p>
            )}
          </div>

          {/* User Notes */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">我的笔记</h2>
              <button
                onClick={() => setIsPreviewMode(!isPreviewMode)}
                className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
              >
                {isPreviewMode ? (
                  <>
                    <Pencil className="w-4 h-4" />
                    编辑
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4" />
                    预览
                  </>
                )}
              </button>
            </div>

            {isPreviewMode ? (
              <div className="min-h-[300px] max-h-[600px] overflow-y-auto border border-gray-200 rounded-lg p-4 bg-gray-50">
                <MarkdownPreview content={userNotes} />
              </div>
            ) : (
              <textarea
                value={userNotes}
                onChange={(event) => setUserNotes(event.target.value)}
                rows={14}
                disabled={isLoading}
                className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 outline-none resize-none font-mono text-sm text-gray-700"
                placeholder="在这里记录你的学习心得、重点难点、参考资源等..."
              />
            )}

            <p className="text-xs text-gray-500 mt-2">
              支持 Markdown 格式 · 点击"预览"查看渲染效果
            </p>
            {saveHint && <p className="text-xs text-gray-500 mt-1">{saveHint}</p>}
          </div>
        </div>
      </div>

      {/* KG Viewer Modal */}
      <KGViewerModal
        taskId={resolvedTaskId}
        isOpen={isKgViewerOpen}
        onClose={() => setIsKgViewerOpen(false)}
      />
    </div>
  );
}
