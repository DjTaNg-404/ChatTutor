import { useParams, useOutletContext } from "react-router";
import { Send, CheckCircle, PanelRightClose, PanelRightOpen, BookOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface Message {
  id: string;
  role: "user" | "assistant" | "divider";
  content: string;
  timestamp: string;
}

interface OutletContext {
  isPanelOpen: boolean;
  setIsPanelOpen: (open: boolean) => void;
}

interface HistorySession {
  session_id: string;
  task_id: string;
  topic: string;
  last_updated: string;
  message_count: number;
}

interface TaskSessionsResponse {
  task_id: string;
  sessions: HistorySession[];
}

interface SessionMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface SessionMessagesResponse {
  session_id: string;
  task_id: string;
  topic: string;
  last_updated: string;
  messages: SessionMessage[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

function formatTime(date = new Date()) {
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function makeMessage(role: "user" | "assistant", content: string): Message {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    timestamp: formatTime(),
  };
}

const taskTitles: { [key: string]: string } = {
  "1": "掌握随机森林算法",
  "2": "雅思口语备考",
  "3": "React Hooks 深入",
  "4": "机器学习数学基础",
};

export function TutorSession() {
  const { taskId } = useParams();
  const context = useOutletContext<OutletContext>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // Provide default values if context is undefined
  const isPanelOpen = context?.isPanelOpen ?? true;
  const setIsPanelOpen = context?.setIsPanelOpen ?? (() => {});

  const taskTitle = taskId ? taskTitles[taskId] || "学习任务" : "欢迎使用 ChatTutor";
  const currentTaskId = taskId ? (taskId.startsWith("task_") ? taskId : `task_${taskId}`) : "task_default";
  const currentDate = new Date().toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  useEffect(() => {
    let isCancelled = false;

    const loadHistory = async () => {
      setIsLoadingHistory(true);
      setErrorText(null);

      try {
        const sessionsResp = await fetch(`${API_BASE_URL}/history/tasks/${currentTaskId}/sessions`);
        if (!sessionsResp.ok) {
          throw new Error(`读取任务会话失败（${sessionsResp.status}）`);
        }

        const sessionsData: TaskSessionsResponse = await sessionsResp.json();
        const latestSession = sessionsData.sessions?.[0];

        if (!latestSession) {
          if (!isCancelled) {
            setActiveSessionId(null);
            setMessages([
              makeMessage("assistant", "你好！我是你的 AI 导师，输入你的问题我们就可以开始学习。"),
            ]);
          }
          return;
        }

        const messageResp = await fetch(`${API_BASE_URL}/history/sessions/${latestSession.session_id}/messages`);
        if (!messageResp.ok) {
          throw new Error(`读取会话消息失败（${messageResp.status}）`);
        }

        const messageData: SessionMessagesResponse = await messageResp.json();
        const historyMessages: Message[] = (messageData.messages || []).map((item) => ({
          id: item.message_id || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role: item.role,
          content: item.content,
          timestamp: item.timestamp ? item.timestamp.slice(11, 16) : formatTime(),
        }));

        if (!isCancelled) {
          setActiveSessionId(messageData.session_id);
          setMessages(
            historyMessages.length > 0
              ? historyMessages
              : [makeMessage("assistant", "你好！我是你的 AI 导师，输入你的问题我们就可以开始学习。")]
          );
        }
      } catch (error) {
        if (!isCancelled) {
          const message = error instanceof Error ? error.message : "读取历史失败";
          setErrorText(message);
          setActiveSessionId(null);
          setMessages([
            makeMessage("assistant", "你好！我是你的 AI 导师，输入你的问题我们就可以开始学习。"),
          ]);
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingHistory(false);
        }
      }
    };

    void loadHistory();
    return () => {
      isCancelled = true;
    };
  }, [currentTaskId]);

  const sendMessage = async (text?: string) => {
    const messageText = text !== undefined ? text : inputText.trim();
    if (!messageText || isSending) return;

    setErrorText(null);
    setMessages((prev) => [...prev, makeMessage("user", messageText)]);
    setInputText("");
    setIsSending(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: currentTaskId,
          session_id: activeSessionId,
          message: text,
          topic: taskTitle,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        const detail = data?.detail || `请求失败（${response.status}）`;
        throw new Error(detail);
      }

      const replyText = data?.reply || "抱歉，我暂时没有生成有效回复。";
      if (data?.session_id) {
        setActiveSessionId(data.session_id);
      }
      setMessages((prev) => [...prev, makeMessage("assistant", replyText)]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "网络异常，请稍后重试。";
      setErrorText(message);
      setMessages((prev) => [
        ...prev,
        makeMessage("assistant", `接口调用失败：${message}`),
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleEndSession = async () => {
    setIsSending(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: currentTaskId,
          session_id: activeSessionId,
          message: "结束并总结今日学习",
          topic: taskTitle,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        const detail = data?.detail || `请求失败（${response.status}）`;
        throw new Error(detail);
      }

      // 添加分割线
      const dividerMessage: Message = {
        id: `${Date.now()}-divider`,
        role: "divider",
        content: "-------------------结束并总结今日学习-------------------",
        timestamp: formatTime(),
      };
      setMessages((prev) => [...prev, dividerMessage]);

      // 添加 AI 的总结回复
      const replyText = data?.reply || "抱歉，我暂时没有生成有效回复。";
      if (data?.session_id) {
        setActiveSessionId(data.session_id);
      }
      setMessages((prev) => [...prev, makeMessage("assistant", replyText)]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "网络异常，请稍后重试。";
      setErrorText(message);
      setMessages((prev) => [
        ...prev,
        makeMessage("assistant", `接口调用失败：${message}`),
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{taskTitle}</h1>
            <p className="text-sm text-gray-500 mt-0.5">{currentDate}</p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to={taskId ? `/task-note/${taskId}` : "/task-note/1"}
              className="flex items-center gap-2 px-4 py-2 bg-white border-2 border-indigo-200 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium"
            >
              <BookOpen className="w-5 h-5" />
              任务笔记
            </Link>
            <button
              onClick={handleEndSession}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
            >
              <CheckCircle className="w-5 h-5" />
              结束并总结今日学习
            </button>
            <button
              onClick={() => setIsPanelOpen(!isPanelOpen)}
              className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
            >
              {isPanelOpen ? (
                <PanelRightClose className="w-5 h-5" />
              ) : (
                <PanelRightOpen className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Chat Messages Area */}
      <div className="flex-1 overflow-y-auto bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {isLoadingHistory && (
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-600">
              正在加载历史对话...
            </div>
          )}

          {errorText && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorText}
            </div>
          )}

          {messages.map((message) => {
            // 渲染分割线
            if (message.role === "divider") {
              return (
                <div
                  key={message.id}
                  className="flex justify-center items-center py-4"
                >
                  <div className="flex items-center gap-4 w-full max-w-2xl">
                    <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
                    <span className="text-gray-400 text-sm font-medium whitespace-nowrap">
                      {message.content}
                    </span>
                    <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
                  </div>
                </div>
              );
            }
            
            return (
              <div
                key={message.id}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] ${
                    message.role === "user"
                      ? "bg-indigo-600 text-white rounded-2xl rounded-tr-sm"
                      : "bg-white border border-gray-200 rounded-2xl rounded-tl-sm"
                  } px-5 py-3 shadow-sm`}
                >
                {/* Message Content with Markdown Support */}
                <div
                  className={`prose prose-sm max-w-none ${
                    message.role === "user"
                      ? "prose-invert"
                      : "prose-gray"
                  }`}
                >
                  {message.role === "user" ? (
                    <p>{message.content}</p>
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                      components={{
                        code({ node, className, children, ...props }) {
                          return (
                            <code
                              className={className || "bg-gray-200 px-1.5 py-0.5 rounded text-sm"}
                              {...props}
                            >
                              {children}
                            </code>
                          );
                        },
                        pre({ node, children, ...props }) {
                          return (
                            <pre
                              className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto my-3"
                              {...props}
                            >
                              {children}
                            </pre>
                          );
                        }
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  )}
                </div>
                
                {/* Timestamp */}
                <div
                  className={`text-xs mt-2 ${
                    message.role === "user"
                      ? "text-indigo-200"
                      : "text-gray-400"
                  }`}
                >
                  {message.timestamp}
                </div>
              </div>
            </div>
            );
          })}
        </div>
      </div>

      {/* Chat Input Footer */}
      <div className="bg-white border-t border-gray-200 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-end gap-3 bg-gray-50 rounded-2xl border border-gray-200 p-3 focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
            <textarea
              placeholder={isSending ? "Tutor 思考中..." : "输入你的问题或想法..."}
              rows={1}
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
              disabled={isSending}
              className="flex-1 bg-transparent border-none outline-none px-2 py-2 text-gray-900 placeholder:text-gray-500 resize-none max-h-32"
              style={{ minHeight: '40px' }}
            />
            <button
              onClick={() => void sendMessage()}
              disabled={isSending || !inputText.trim()}
              className="p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <p className="text-xs text-gray-500 text-center mt-2">
            按 Enter 发送，Shift + Enter 换行
          </p>
        </div>
      </div>
    </div>
  );
}