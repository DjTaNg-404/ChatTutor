import { useState, useEffect } from "react";
import { X, RefreshCw, AlertCircle, CheckCircle2, ExternalLink } from "lucide-react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
const STREAMLIT_KG_URL = "http://localhost:8501";

interface KGViewerModalProps {
  taskId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function KGViewerModal({ taskId, isOpen, onClose }: KGViewerModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isBuilding, setIsBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buildSuccess, setBuildSuccess] = useState(false);
  const [kgExists, setKgExists] = useState<boolean | null>(null);
  const [iframeKey, setIframeKey] = useState(0); // 用于强制刷新 iframe

  const checkKGStatus = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/kg/get-task-kg?task_id=${encodeURIComponent(taskId)}`
      );
      if (!response.ok) {
        throw new Error("检查知识图谱状态失败");
      }
      const data = await response.json();
      setKgExists(data.exists);
      if (!data.exists) {
        setError("知识图谱尚未生成，请点击下方按钮构建");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "检查失败");
    } finally {
      setIsLoading(false);
    }
  };

  const buildKG = async () => {
    setIsBuilding(true);
    setError(null);
    setBuildSuccess(false);
    try {
      const response = await fetch(`${API_BASE_URL}/kg/build-from-task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: taskId,
          use_deepseek: true,
          deepseek_model: "deepseek-chat",
          force_rebuild: true, // 强制重新生成
        }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "构建知识图谱失败");
      }
      const data = await response.json();
      if (data.kg_exists) {
        setBuildSuccess(false);
      } else {
        setBuildSuccess(true);
        setKgExists(true);
        setError(null);
        // 刷新 iframe
        setIframeKey((prev) => prev + 1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "构建失败");
    } finally {
      setIsBuilding(false);
    }
  };

  useEffect(() => {
    if (isOpen && taskId) {
      checkKGStatus();
    }
  }, [isOpen, taskId]);

  useEffect(() => {
    if (buildSuccess) {
      const timer = setTimeout(() => setBuildSuccess(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [buildSuccess]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-xl w-[95vw] h-[95vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold text-white">知识图谱</h2>
            {buildSuccess && (
              <span className="flex items-center gap-1 text-green-400 text-sm">
                <CheckCircle2 className="w-4 h-4" />
                已更新
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <a
              href={`${STREAMLIT_KG_URL}/?task_id=${taskId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span className="text-sm font-medium">独立窗口打开</span>
            </a>
            <button
              onClick={buildKG}
              disabled={isBuilding}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isBuilding ? "animate-spin" : ""}`} />
              <span className="text-sm font-medium">
                {isBuilding ? "构建中..." : "更新知识图谱"}
              </span>
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 relative bg-gray-800">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <RefreshCw className="w-8 h-8 text-purple-400 animate-spin" />
            </div>
          ) : error && !kgExists ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-yellow-400 mx-auto mb-3" />
                <p className="text-gray-300 mb-4">{error}</p>
                <button
                  onClick={buildKG}
                  disabled={isBuilding}
                  className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
                >
                  立即构建
                </button>
              </div>
            </div>
          ) : (
            <iframe
              key={iframeKey}
              src={`${STREAMLIT_KG_URL}/?task_id=${taskId}`}
              className="w-full h-full border-0"
              title="Knowledge Graph Viewer"
              allow="fullscreen"
            />
          )}
        </div>
      </div>
    </div>
  );
}
