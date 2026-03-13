import { useEffect, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router";
import { ArrowLeft, Calendar, Edit3, Save, Sparkles, Wand2, Eye, Pencil } from "lucide-react";
import { MarkdownPreview } from "./MarkdownPreview";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

interface DailyNoteApiResponse {
  task_id: string;
  date: string;
  content: string;
  updated_at: string;
}

interface DailySummaryAiSummary {
  key_learnings: string[];
  review_areas: string[];
  achievements: string[];
}

interface DailySummaryResponse {
  task_id: string;
  date: string;
  summary: string;
  ai_summary: DailySummaryAiSummary;
  created_at: string;
}

interface DailyNote {
  date: string;
  taskTitle: string;
  aiSummary: {
    keyLearnings: string[];
    reviewAreas: string[];
    achievements: string[];
  };
  userNotes: string;
}

export function DailyNotePage() {
  const { date } = useParams<{ date: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const resolvedDate = date || new Date().toISOString().slice(0, 10);
  const resolvedTaskId = searchParams.get("task_id") || "";
  const hasTaskId = Boolean(resolvedTaskId);
  const [userNotes, setUserNotes] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [saveHint, setSaveHint] = useState<string | null>(null);
  const [aiSummary, setAiSummary] = useState<DailyNote["aiSummary"]>({ keyLearnings: [], reviewAreas: [], achievements: [] });
  const [isPreviewMode, setIsPreviewMode] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadDailyNote = async () => {
      if (!hasTaskId) {
        setUserNotes("");
        setAiSummary({ keyLearnings: [], reviewAreas: [], achievements: [] });
        setSaveHint("缺少 task_id，无法加载笔记。");
        return;
      }

      setIsLoading(true);
      setSaveHint(null);
      try {
        const response = await fetch(
          `${API_BASE_URL}/notes/daily?task_id=${encodeURIComponent(resolvedTaskId)}&date=${encodeURIComponent(resolvedDate)}`
        );
        if (!response.ok) {
          throw new Error(`加载每日笔记失败（${response.status}）`);
        }
        const data: DailyNoteApiResponse = await response.json();
        if (!cancelled) {
          setUserNotes(data.content || "");
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "加载每日笔记失败";
          setSaveHint(message);
          setUserNotes("");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadDailyNote();
    return () => {
      cancelled = true;
    };
  }, [resolvedTaskId, resolvedDate, hasTaskId]);

  const handleSave = async () => {
    if (!hasTaskId) {
      setSaveHint("缺少 task_id，无法保存。");
      return;
    }

    setIsSaving(true);
    setSaveHint(null);
    try {
      const response = await fetch(`${API_BASE_URL}/notes/daily`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: resolvedTaskId,
          date: resolvedDate,
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

  const handleGenerateSummary = async () => {
    if (!hasTaskId) {
      setSaveHint("缺少 task_id，无法生成总结。");
      return;
    }

    setIsGeneratingSummary(true);
    setSaveHint(null);
    try {
      const response = await fetch(`${API_BASE_URL}/history/tasks/${resolvedTaskId}/daily-summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: resolvedTaskId,
          date: resolvedDate,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `生成总结失败（${response.status}）`);
      }

      const data: DailySummaryResponse = await response.json();

      // 更新用户笔记内容为生成的总结
      setUserNotes(data.summary);
      // 更新 AI 总结显示
      setAiSummary({
        keyLearnings: data.ai_summary.key_learnings || [],
        reviewAreas: data.ai_summary.review_areas || [],
        achievements: data.ai_summary.achievements || [],
      });
      setSaveHint("已生成今日学习总结");
    } catch (error) {
      const message = error instanceof Error ? error.message : "生成总结失败";
      setSaveHint(message);
    } finally {
      setIsGeneratingSummary(false);
    }
  };

  // 格式化日期显示
  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    const [year, month, day] = dateStr.split("-");
    return `${year}年${month}月${day}日`;
  };

  const displayData: DailyNote = {
    date: resolvedDate,
    taskTitle: "学习任务",
    aiSummary: aiSummary,
    userNotes: "",
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-3 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm font-medium">返回</span>
          </button>

          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-indigo-100 rounded-lg">
                  <Edit3 className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <h1 className="text-2xl font-semibold text-gray-900">
                    {displayData.taskTitle} - 学习笔记
                  </h1>
                  <p className="text-sm text-gray-600 mt-0.5">
                    {formatDate(displayData.date)}
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={() => void handleSave()}
              disabled={isSaving || isLoading || !hasTaskId}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              <Save className="w-4 h-4" />
              <span className="text-sm font-medium">{isSaving ? "保存中..." : "保存笔记"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* AI Generated Summary */}
          <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl border border-indigo-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-600" />
                <h2 className="text-lg font-semibold text-gray-900">AI 学习总结</h2>
                <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-medium ml-2">
                  自动生成
                </span>
              </div>

              <button
                onClick={() => void handleGenerateSummary()}
                disabled={isGeneratingSummary || isLoading || !hasTaskId}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
              >
                <Wand2 className="w-4 h-4" />
                {isGeneratingSummary ? "生成中..." : "生成单日总结"}
              </button>
            </div>

            {/* Key Learnings */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                📚 今日学习要点
              </h3>
              <ul className="space-y-2">
                {displayData.aiSummary.keyLearnings.map((learning, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-sm text-gray-700 bg-white rounded-lg p-3"
                  >
                    <span className="text-indigo-600 font-semibold mt-0.5">
                      {idx + 1}.
                    </span>
                    <span className="flex-1">{learning}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Achievements */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                ✨ 学习成果
              </h3>
              <ul className="space-y-2">
                {displayData.aiSummary.achievements.map((achievement, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-sm text-gray-700 bg-white rounded-lg p-3"
                  >
                    <span className="text-green-500 mt-0.5">✓</span>
                    <span className="flex-1">{achievement}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Review Areas */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                🔄 待复习内容
              </h3>
              <ul className="space-y-2">
                {displayData.aiSummary.reviewAreas.map((area, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-sm text-amber-700 bg-white rounded-lg p-3"
                  >
                    <span className="text-amber-500 mt-0.5">⚠</span>
                    <span className="flex-1">{area}</span>
                  </li>
                ))}
              </ul>
            </div>
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
                rows={12}
                disabled={isLoading}
                className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 outline-none resize-none font-mono text-sm text-gray-700"
                placeholder="在这里添加你的个人学习笔记、心得体会或问题..."
              />
            )}

            <p className="text-xs text-gray-500 mt-2">
              支持 Markdown 格式 · 点击"预览"查看渲染效果
            </p>
            {saveHint && <p className="text-xs text-gray-500 mt-1">{saveHint}</p>}
          </div>

          {/* Quick Actions */}
          <div className="flex items-center justify-between bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Calendar className="w-4 h-4" />
              <span>最后编辑：今天 14:32</span>
            </div>
            <div className="flex items-center gap-3">
              <button className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
                导出为 PDF
              </button>
              <button className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
                分享笔记
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
