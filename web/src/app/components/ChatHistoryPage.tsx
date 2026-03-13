import { useEffect, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router";
import { ArrowLeft, Calendar, Clock, Download, Share2 } from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
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

interface SessionMessageItem {
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
  messages: SessionMessageItem[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export function ChatHistoryPage() {
  const { date } = useParams<{ date: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const taskIdFromQuery = searchParams.get("task_id") || "task_default";
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [taskTitle, setTaskTitle] = useState("学习记录");
  const [isLoading, setIsLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const getDateFromSessionId = (sessionId: string) => {
    const parts = sessionId.split("__");
    if (parts.length < 2) return "";
    const raw = parts[1];
    if (raw.length !== 8 || !/^\d{8}$/.test(raw)) return "";
    return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
  };

  useEffect(() => {
    if (!date) {
      setMessages([]);
      return;
    }

    let cancelled = false;

    const loadHistory = async () => {
      setIsLoading(true);
      setErrorText(null);
      try {
        const sessionsResp = await fetch(`${API_BASE_URL}/history/tasks/${taskIdFromQuery}/sessions`);
        if (!sessionsResp.ok) {
          throw new Error(`读取会话列表失败（${sessionsResp.status}）`);
        }

        const sessionsData: TaskSessionsResponse = await sessionsResp.json();
        const sameDaySessions = (sessionsData.sessions || []).filter((session) => {
          const byUpdated = session.last_updated?.startsWith(date);
          const byIdDate = getDateFromSessionId(session.session_id) === date;
          return Boolean(byUpdated || byIdDate);
        });

        if (sameDaySessions.length === 0) {
          if (!cancelled) {
            setTaskTitle("学习记录");
            setMessages([]);
          }
          return;
        }

        const historyResponses = await Promise.all(
          sameDaySessions.map(async (session) => {
            const resp = await fetch(`${API_BASE_URL}/history/sessions/${session.session_id}/messages`);
            if (!resp.ok) {
              throw new Error(`读取会话消息失败（${resp.status}）`);
            }
            const data: SessionMessagesResponse = await resp.json();
            return { session, data };
          })
        );

        const mergedMessages: ChatMessage[] = historyResponses
          .flatMap(({ data }) => data.messages || [])
          .map((item, index) => ({
            id: item.message_id || `history-${index}`,
            role: item.role,
            content: item.content,
            timestamp: item.timestamp ? item.timestamp.slice(11, 16) : "--:--",
          }));

        if (!cancelled) {
          setTaskTitle(historyResponses[0]?.data.topic || "学习记录");
          setMessages(mergedMessages);
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "读取历史记录失败";
          setErrorText(message);
          setMessages([]);
          setTaskTitle("学习记录");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [date, taskIdFromQuery]);

  // 格式化日期显示
  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    const [year, month, day] = dateStr.split("-");
    return `${year}年${month}月${day}日`;
  };

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
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-indigo-100 rounded-lg">
                  <Calendar className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <h1 className="text-2xl font-semibold text-gray-900">
                    {taskTitle}
                  </h1>
                  <p className="text-sm text-gray-600 mt-0.5">
                    {date && formatDate(date)} 的学习记录
                  </p>
                  <p className="text-xs text-gray-500 mt-1">任务：{taskIdFromQuery}</p>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                <Share2 className="w-4 h-4 text-gray-600" />
                <span className="text-sm font-medium text-gray-700">分享</span>
              </button>
              <button className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">
                <Download className="w-4 h-4" />
                <span className="text-sm font-medium">导出记录</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Chat History Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto">
          {isLoading && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 text-sm text-gray-600">
              正在加载历史记录...
            </div>
          )}

          {errorText && (
            <div className="bg-red-50 rounded-xl border border-red-200 p-4 mb-4 text-sm text-red-700">
              {errorText}
            </div>
          )}

          {/* Session Info Card */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-indigo-50 rounded-xl">
                  <Clock className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">学习时长</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    约 {messages.length > 0 ? Math.ceil(messages.length * 2.5) : 0} 分钟
                  </p>
                </div>
              </div>
              <div className="text-right">
                <h3 className="font-semibold text-gray-900">对话轮次</h3>
                <p className="text-sm text-gray-600 mt-1">
                  {messages.length} 条消息
                </p>
              </div>
            </div>
          </div>

          {/* Messages */}
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Calendar className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-gray-500">暂无此日期的学习记录</p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message, index) => (
                <div key={message.id}>
                  {/* Time Marker for first message or when time gap is significant */}
                  {index === 0 && (
                    <div className="flex items-center justify-center mb-6">
                      <div className="px-4 py-1.5 bg-gray-100 rounded-full text-xs font-medium text-gray-600">
                        {message.timestamp}
                      </div>
                    </div>
                  )}

                  <div
                    className={`flex ${
                      message.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[75%] ${
                        message.role === "user"
                          ? "bg-indigo-600 text-white rounded-2xl rounded-tr-sm"
                          : "bg-white border border-gray-200 rounded-2xl rounded-tl-sm"
                      } px-5 py-4 shadow-sm`}
                    >
                      {/* Message Content with Markdown Support */}
                      <div
                        className={`prose prose-sm max-w-none ${
                          message.role === "user"
                            ? "prose-invert"
                            : "prose-gray"
                        }`}
                      >
                        {message.content.split('\n\n').map((paragraph, idx) => {
                          // Handle code blocks
                          if (paragraph.startsWith('```')) {
                            const codeMatch = paragraph.match(/```(\w+)?\n([\s\S]*?)```/);
                            if (codeMatch) {
                              return (
                                <pre key={idx} className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto my-3">
                                  <code className="text-sm font-mono">{codeMatch[2]}</code>
                                </pre>
                              );
                            }
                          }
                          
                          // Handle headings
                          if (paragraph.startsWith('## ')) {
                            return (
                              <h2 key={idx} className="text-base font-semibold mt-4 mb-2">
                                {paragraph.replace('## ', '')}
                              </h2>
                            );
                          }
                          
                          // Handle tables
                          if (paragraph.includes('|')) {
                            const rows = paragraph.split('\n').filter(row => row.includes('|'));
                            if (rows.length > 1) {
                              return (
                                <div key={idx} className="overflow-x-auto my-3">
                                  <table className="min-w-full border-collapse border border-gray-300">
                                    <thead>
                                      <tr className="bg-gray-50">
                                        {rows[0].split('|').filter(cell => cell.trim()).map((cell, i) => (
                                          <th key={i} className="border border-gray-300 px-3 py-2 text-left text-sm font-semibold">
                                            {cell.trim()}
                                          </th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {rows.slice(2).map((row, i) => (
                                        <tr key={i}>
                                          {row.split('|').filter(cell => cell.trim()).map((cell, j) => (
                                            <td key={j} className="border border-gray-300 px-3 py-2 text-sm">
                                              {cell.trim()}
                                            </td>
                                          ))}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              );
                            }
                          }
                          
                          // Handle lists
                          if (paragraph.includes('\n   - ') || paragraph.includes('\n- ')) {
                            const items = paragraph.split('\n').filter(line => line.trim());
                            return (
                              <ul key={idx} className="space-y-1 my-2 list-disc pl-5">
                                {items.map((item, i) => {
                                  const cleaned = item.replace(/^[\s\-]+/, '').trim();
                                  return cleaned && <li key={i}>{cleaned}</li>;
                                })}
                              </ul>
                            );
                          }
                          
                          // Handle bold text
                          const parts = paragraph.split(/\*\*(.*?)\*\*/g);
                          return (
                            <p key={idx} className="my-2 leading-relaxed">
                              {parts.map((part, i) =>
                                i % 2 === 1 ? <strong key={i}>{part}</strong> : part
                              )}
                            </p>
                          );
                        })}
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
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
