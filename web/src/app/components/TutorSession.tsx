import { useParams, useOutletContext } from "react-router";
import { Send, CheckCircle, PanelRightClose, PanelRightOpen, BookOpen, Square } from "lucide-react";
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
  planProposal?: TaskPlan;
  planConfirmed?: boolean;
  planError?: string;
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

interface StreamEvent {
  event: "start" | "delta" | "done" | "error" | "interrupted" | "intent" | "progress";
  data: Record<string, any>;
}

interface TaskPlan {
  task_id?: string;
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
  _plan_sig?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
const ENABLE_STREAMING = (import.meta.env.VITE_ENABLE_STREAMING ?? "true").toString().toLowerCase() !== "false";
const TASK_DRAFT_KEY = "task_draft";

function loadDraftTask() {
  try {
    const raw = localStorage.getItem(TASK_DRAFT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (data && typeof data.id === "string") {
      return {
        id: data.id as string,
        title: (data.title as string) || "新的学习",
        icon: (data.icon as string) || "✨",
      };
    }
  } catch {
    return null;
  }
  return null;
}

function clearDraftTask() {
  try {
    localStorage.removeItem(TASK_DRAFT_KEY);
  } catch {
    // ignore
  }
}

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

export function TutorSession() {
  const { taskId } = useParams();
  const context = useOutletContext<OutletContext>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [confirmingPlanId, setConfirmingPlanId] = useState<string | null>(null);
  const [taskTitleDisplay, setTaskTitleDisplay] = useState("学习任务");
  const [intentDisplay, setIntentDisplay] = useState<string>("");
  const [showIntentDisplay, setShowIntentDisplay] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [showAcceptNoteButton, setShowAcceptNoteButton] = useState(false);
  const [isAcceptingNote, setIsAcceptingNote] = useState(false);
  const [draftTask, setDraftTask] = useState<{ id: string; title: string; icon: string } | null>(() =>
    loadDraftTask()
  );
  const [planStatus, setPlanStatus] = useState<string | null>(null);

  const normalizePlanSteps = (plan?: TaskPlan | null): string[] => {
    if (!plan) return [];
    const raw = (plan as { plan?: unknown }).plan;
    if (Array.isArray(raw)) {
      return raw.map((item) => String(item)).filter((item) => item.trim());
    }
    if (typeof raw === "string") {
      return raw
        .split(/\r?\n|[；;]+/)
        .map((item) => item.trim())
        .filter(Boolean);
    }
    if (plan.overallSummary) {
      return [plan.overallSummary];
    }
    return [];
  };

  const readStreamResponse = async (
    response: Response,
    assistantId: string,
  ): Promise<{ sessionId?: string; isConcluded?: boolean; planProposal?: TaskPlan | null; intentDisplay?: string; planStatus?: string | null }> => {
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("流式响应不可读");
    }

    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalSessionId: string | undefined;
    let finalConcluded = false;
    let finalPlan: TaskPlan | null = null;
    let finalIntentDisplay: string | undefined;
    let finalPlanStatus: string | null | undefined;
    let interrupted = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let idx = buffer.indexOf("\n");
      while (idx >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (line) {
          const evt = JSON.parse(line) as StreamEvent;
          if (evt.event === "delta") {
            const delta = String(evt.data?.text ?? "");
            if (delta) {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + delta } : m)),
              );
            }
          } else if (evt.event === "intent") {
            // 意图识别事件
            if (evt.data?.text) {
              setIntentDisplay(evt.data.text);
              setShowIntentDisplay(true);
              // 3 秒后隐藏意图识别文字
              setTimeout(() => {
                setShowIntentDisplay(false);
                setIntentDisplay("");
              }, 3000);
            }
          } else if (evt.event === "progress") {
            // 进度事件（进入 xx 模式）
            if (evt.data?.text) {
              setIntentDisplay(evt.data.text);
              setShowIntentDisplay(true);
              // 3 秒后隐藏
              setTimeout(() => {
                setShowIntentDisplay(false);
                setIntentDisplay("");
              }, 3000);
            }
          } else if (evt.event === "interrupted") {
            // 中断事件
            interrupted = true;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + "\n\n[已停止生成]" }
                  : m
              )
            );
          } else if (evt.event === "done") {
            if (evt.data?.session_id) {
              finalSessionId = String(evt.data.session_id);
            }
            finalConcluded = Boolean(evt.data?.is_concluded);
            if (evt.data?.plan_proposal) {
              finalPlan = evt.data.plan_proposal as TaskPlan;
            }
            if (typeof evt.data?.plan_status !== "undefined") {
              finalPlanStatus = evt.data.plan_status as string | null;
            }
            if (evt.data?.intent_display) {
              finalIntentDisplay = String(evt.data.intent_display);
            }
            // 如果是总结完成，显示接受笔记更新按钮
            if (finalConcluded) {
              setShowAcceptNoteButton(true);
            }
          } else if (evt.event === "error") {
            const err = evt.data?.message || "流式响应失败";
            throw new Error(String(err));
          }
        }
        idx = buffer.indexOf("\n");
      }
    }

    // 如果被中断，不要返回正常的完成状态
    if (interrupted) {
      setIsSending(false);
      return { sessionId: finalSessionId, isConcluded: false, planProposal: null, intentDisplay: "" };
    }

    return { sessionId: finalSessionId, isConcluded: finalConcluded, planProposal: finalPlan, intentDisplay: finalIntentDisplay, planStatus: finalPlanStatus };
  };

  const fallbackSendMessage = async (messageText: string) => {
    const planHint = false;
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        task_id: currentTaskId,
        session_id: activeSessionId,
        message: messageText,
        topic: taskTitleDisplay,
        plan_hint: planHint,
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
    if (typeof data?.plan_status !== "undefined") {
      setPlanStatus(data.plan_status ?? null);
    }
    const assistantMessage = makeMessage("assistant", replyText);
    if (data?.plan_proposal) {
      assistantMessage.planProposal = data.plan_proposal as TaskPlan;
    }
    setMessages((prev) => [...prev, assistantMessage]);

    // 设置意图识别展示文字
    if (data?.intent_display) {
      setIntentDisplay(data.intent_display);
      setShowIntentDisplay(true);
      // 3 秒后隐藏意图识别文字
      setTimeout(() => {
        setShowIntentDisplay(false);
        setIntentDisplay("");
      }, 3000);
    }

    // 如果是总结请求，重置 isSummarizing 状态并显示接受笔记更新按钮
    if (data?.is_concluded) {
      setIsSummarizing(false);
      setShowAcceptNoteButton(true);
    } else {
      // 备用逻辑：如果用户发送的是"生成学习总结"，也显示按钮
      if (messageText === "生成学习总结") {
        setShowAcceptNoteButton(true);
      }
    }
  };

  // Provide default values if context is undefined
  const isPanelOpen = context?.isPanelOpen ?? true;
  const setIsPanelOpen = context?.setIsPanelOpen ?? (() => {});

  const currentTaskId = taskId ? (taskId.startsWith("task_") ? taskId : `task_${taskId}`) : "task_default";
  const isDraftTask = Boolean(draftTask && currentTaskId === draftTask.id);
  const isPlanActive = Boolean(
    planStatus && ["await_confirm", "await_plan_confirm", "collecting"].includes(planStatus)
  );
  const isPlanPaused = planStatus === "paused";
  const currentDate = new Date().toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  useEffect(() => {
    const handleTasksUpdated = () => {
      setDraftTask(loadDraftTask());
    };
    window.addEventListener("tasks-updated", handleTasksUpdated);
    return () => {
      window.removeEventListener("tasks-updated", handleTasksUpdated);
    };
  }, []);
  useEffect(() => {
    let cancelled = false;
    const fallbackTitle = taskId ? "学习任务" : "欢迎使用 ChatTutor";

    if (isDraftTask) {
      setTaskTitleDisplay(draftTask?.title || "新的学习");
      return () => {
        cancelled = true;
      };
    }

    const loadTaskTitle = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/notes/task?task_id=${currentTaskId}`);
        if (!response.ok) {
          throw new Error("failed");
        }
        const data = await response.json();
        const resolved = data?.taskTitle || fallbackTitle;
        if (!cancelled) {
          setTaskTitleDisplay(resolved);
        }
      } catch {
        if (!cancelled) {
          setTaskTitleDisplay(fallbackTitle);
        }
      }
    };

    void loadTaskTitle();
    return () => {
      cancelled = true;
    };
  }, [currentTaskId, taskId]);
  useEffect(() => {
    let isCancelled = false;

    const loadHistory = async () => {
      setIsLoadingHistory(true);
      setErrorText(null);

      if (isDraftTask) {
        setActiveSessionId(null);
        setPlanStatus(null);
        setMessages([
          makeMessage("assistant", "你好，我是你的 AI 导师，输入你的问题我们就可以开始学习。"),
        ]);
        setIsLoadingHistory(false);
        return;
      }

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

        let draftPlan: TaskPlan | null = null;
        try {
          const planResp = await fetch(`${API_BASE_URL}/notes/task?task_id=${currentTaskId}`);
          if (planResp.ok) {
            const planData = await planResp.json();
            if (planData?.draft_plan && typeof planData.draft_plan === "object") {
              draftPlan = planData.draft_plan as TaskPlan;
            }
            if (typeof planData?._plan_session?.status !== "undefined") {
              setPlanStatus(planData._plan_session.status as string);
            } else {
              setPlanStatus(null);
            }
          }
        } catch {
          draftPlan = null;
          setPlanStatus(null);
        }

        if (draftPlan && historyMessages.length > 0) {
          const revIdx = [...historyMessages].reverse().findIndex((msg) => msg.role === "assistant");
          if (revIdx >= 0) {
            const idx = historyMessages.length - 1 - revIdx;
            if (!historyMessages[idx].planProposal) {
              historyMessages[idx] = { ...historyMessages[idx], planProposal: draftPlan };
            }
          } else {
            const draftMsg = makeMessage("assistant", "?????????????????");
            draftMsg.planProposal = draftPlan;
            historyMessages.push(draftMsg);
          }
        } else if (draftPlan && historyMessages.length === 0) {
          const draftMsg = makeMessage("assistant", "?????????????????");
          draftMsg.planProposal = draftPlan;
          historyMessages.push(draftMsg);
        }


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

  useEffect(() => {
    return () => {
      const draft = loadDraftTask();
      if (draft && draft.id === currentTaskId) {
        clearDraftTask();
        window.dispatchEvent(new Event("tasks-updated"));
      }
    };
  }, [currentTaskId]);

  const ensureDraftTaskCreated = async () => {
    const draft = loadDraftTask();
    if (!draft || draft.id !== currentTaskId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: draft.id,
          title: draft.title || "新的学习",
          icon: draft.icon || "✨",
          status: "active",
        }),
      });
      if (response.ok) {
        clearDraftTask();
        setDraftTask(null);
        window.dispatchEvent(new Event("tasks-updated"));
      }
    } catch {
      // ignore creation failures
    }
  };

  const sendMessage = async (text?: string) => {
    const messageText = text !== undefined ? text : inputText.trim();
    if (!messageText || isSending) return;

    if (isDraftTask) {
      await ensureDraftTaskCreated();
    }

    setErrorText(null);
    setIntentDisplay(""); // 清空意图识别显示
    setMessages((prev) => [...prev, makeMessage("user", messageText)]);
    setInputText("");
    setIsSending(true);

    // 如果是生成学习总结的消息，先隐藏按钮
    if (messageText === "生成学习总结") {
      setShowAcceptNoteButton(false);
    }

    // 创建 AbortController 用于取消请求
    const controller = new AbortController();
    setAbortController(controller);

    try {
      if (!ENABLE_STREAMING) {
        await fallbackSendMessage(messageText);
        return;
      }

      const assistantId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          timestamp: formatTime(),
        },
      ]);

      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: currentTaskId,
          session_id: activeSessionId,
          message: messageText,
            topic: taskTitleDisplay,
          plan_hint: false,
        }), signal: controller.signal });

      if (!response.ok) {
        throw new Error(`请求失败（${response.status}）`);
      }

      const streamResult = await readStreamResponse(response, assistantId);
      if (streamResult.sessionId) {
        setActiveSessionId(streamResult.sessionId);
      }
      if (typeof streamResult.planStatus !== "undefined") {
        setPlanStatus(streamResult.planStatus ?? null);
      }
      if (streamResult.planProposal) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, planProposal: streamResult.planProposal } : m
          )
        );
      }
      // 设置意图识别展示文字
      if (streamResult.intentDisplay) {
        setIntentDisplay(streamResult.intentDisplay);
        setShowIntentDisplay(true);
        // 3 秒后隐藏意图识别文字
        setTimeout(() => {
          setShowIntentDisplay(false);
          setIntentDisplay("");
        }, 3000);
      }
      // 如果总结完成，重置 isSummarizing 状态并显示按钮
      if (streamResult.isConcluded) {
        setIsSummarizing(false);
        setShowAcceptNoteButton(true);
      } else {
        // 备用逻辑：如果用户发送的是"生成学习总结"，也显示按钮
        if (messageText === "生成学习总结") {
          setShowAcceptNoteButton(true);
        }
      }
    } catch (error) {
      try {
        await fallbackSendMessage(messageText);
      } catch (fallbackError) {
        const message = fallbackError instanceof Error ? fallbackError.message : "网络异常，请稍后重试。";
        setErrorText(message);
        setMessages((prev) => [
          ...prev,
          makeMessage("assistant", `接口调用失败：${message}`),
        ]);
      }
    } finally {
      setIsSending(false);
      setAbortController(null);

      // 发送消息后，触发时间线更新事件
      window.dispatchEvent(new Event("timeline-updated"));
    }
  };

  useEffect(() => {
    const handleRequestPlan = (event: Event) => {
      const detail = (event as CustomEvent).detail as { taskId?: string } | undefined;
      if (detail?.taskId && detail.taskId !== currentTaskId) {
        return;
      }
      if (isSending || showIntentDisplay) return;
      void sendMessage("帮我生成一份学习计划。");
    };
    window.addEventListener("request-plan", handleRequestPlan);
    return () => {
      window.removeEventListener("request-plan", handleRequestPlan);
    };
  }, [currentTaskId, isSending, showIntentDisplay]);
  const handleStopGeneration = async () => {
    if (abortController && activeSessionId) {
      // 调用后端中断接口
      try {
        await fetch(`${API_BASE_URL}/chat/interrupt`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            session_id: activeSessionId,
          }),
        });
      } catch (error) {
        console.error("中断请求失败:", error);
      }
      // 取消前端请求
      abortController.abort();
      setAbortController(null);
      setIsSending(false);
    }
  };

  const handleEndSession = async () => {
    if (isSummarizing) return; // 防止重复点击

    // 添加分割线
    const dividerMessage: Message = {
      id: `${Date.now()}-divider`,
      role: "divider",
      content: "-------------------生成学习总结-------------------",
      timestamp: formatTime(),
    };
    setMessages((prev) => [...prev, dividerMessage]);

    setIsSummarizing(true);
    setShowAcceptNoteButton(false); // 重置按钮状态
    await sendMessage("生成学习总结");
    // 注意：isSummarizing 会在总结完成后由 stream 结果自动重置
  };

  const handleAcceptNoteUpdate = async () => {
    setIsAcceptingNote(true);
    setShowAcceptNoteButton(false);
    try {
      // 调用后端任务总结 API（对整个任务的所有对话生成总结）
      const taskSummaryResp = await fetch(
        `${API_BASE_URL}/history/tasks/${currentTaskId}/summary`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            task_id: currentTaskId,
          }),
        }
      );

      if (!taskSummaryResp.ok) {
        throw new Error(`获取任务总结失败（${taskSummaryResp.status}）`);
      }

      // 等待后端保存完成
      await new Promise(resolve => setTimeout(resolve, 500));

      // 触发任务计划更新事件
      window.dispatchEvent(new Event("task-plan-updated"));

      // 结束计划状态（如果当前处于计划中）
      if (planStatus && ["await_confirm", "await_plan_confirm", "collecting", "paused"].includes(planStatus)) {
        await applyPlanSessionAction("exit");
        setPlanStatus(null);
      }

      // 显示成功提示
      const successMessage: Message = {
        id: `${Date.now()}-note-accepted`,
        role: "assistant",
        content: "✅ 已将任务学习总结更新到任务笔记。点击右上角【任务笔记】按钮查看。",
        timestamp: formatTime(),
      };
      setMessages((prev) => [...prev, successMessage]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "更新失败";
      const errorMessage: Message = {
        id: `${Date.now()}-note-error`,
        role: "assistant",
        content: `❌ 更新笔记失败：${message}`,
        timestamp: formatTime(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsAcceptingNote(false);
    }
  };

  const confirmPlanUpdate = async (messageId: string, plan: TaskPlan) => {
    setConfirmingPlanId(messageId);
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, planError: undefined } : m))
    );
    try {
      // 确认学习计划（后端会自动更新任务笔记）
      const response = await fetch(`${API_BASE_URL}/agent/task-plan/confirm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: currentTaskId,
          plan,
        }),
      });
      if (!response.ok) {
        throw new Error(`请求失败（${response.status}）`);
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, planConfirmed: true } : m
        )
      );

      // 触发任务计划和时间线更新事件
      window.dispatchEvent(new Event("task-plan-updated"));
      window.dispatchEvent(new Event("timeline-updated"));
    } catch (error) {
      const message = error instanceof Error ? error.message : "更新失败";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, planError: message } : m
        )
      );
    } finally {
      setConfirmingPlanId(null);
    }
  };

  const applyPlanSessionAction = async (action: "resume" | "exit") => {
    try {
      const response = await fetch(`${API_BASE_URL}/agent/task-plan/session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: currentTaskId,
          action,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        const status = typeof data?.status === "string" ? data.status : null;
        setPlanStatus(status === "idle" ? null : status);
      }
    } catch {
      // ignore; keep local state unchanged
    }
  };

  const handleResumePlan = async () => {
    setPlanStatus("collecting");
    await applyPlanSessionAction("resume");
    setMessages((prev) => [
      ...prev,
      makeMessage("assistant", "好的，我们继续调整学习计划。请告诉我你想修改哪些内容。"),
    ]);
  };

  const handleExitPlan = async () => {
    setPlanStatus(null);
    await applyPlanSessionAction("exit");
    setMessages((prev) => [
      ...prev,
      makeMessage("assistant", "好的，已结束学习计划规划。如需再规划，随时告诉我。"),
    ]);
  };

  return (
    <div className="flex flex-col h-full">
      <style>
        {`
          @keyframes typing-bounce {
            0%, 80%, 100% { transform: translateY(0) scale(0.9); opacity: 0.6; }
            40% { transform: translateY(-6px) scale(1.05); opacity: 1; }
          }
        `}
      </style>
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{taskTitleDisplay}</h1>
            <p className="text-sm text-gray-500 mt-0.5">{currentDate}</p>
            {isPlanActive && (
              <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium px-3 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                计划调整中
              </div>
            )}
            {isPlanPaused && (
              <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-amber-50 text-amber-700 text-xs font-medium px-3 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                计划已挂起，等待继续
              </div>
            )}
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
              disabled={isSummarizing}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <CheckCircle className="w-5 h-5" />
              更新任务笔记
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

                  {message.role === "assistant" && message.planProposal && (
                    <div className="mt-3 border-t border-gray-200 pt-3">
                      <div className="text-xs font-semibold text-gray-500 mb-2">详细学习计划（确认后更新）</div>
                      <div className="space-y-2 text-sm text-gray-700">
                        <div className="font-medium text-gray-900">
                          {message.planProposal.taskTitle || "学习计划"}
                        </div>
                        {message.planProposal.overallSummary && (
                          <div className="text-xs text-gray-600">
                            {message.planProposal.overallSummary}
                          </div>
                        )}
                        <div className="text-xs text-gray-500">
                          {(message.planProposal.totalDays ?? 0) > 0 && (
                            <span>{message.planProposal.totalDays} 天</span>
                          )}
                          {(message.planProposal.totalHours ?? 0) > 0 && (
                            <span> · {message.planProposal.totalHours} 小时</span>
                          )}
                        </div>
                        {normalizePlanSteps(message.planProposal).length > 0 && (
                          <ul className="text-xs text-gray-700 space-y-1">
                            {normalizePlanSteps(message.planProposal).map((step, idx) => (
                              <li key={idx}>• {step}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div className="mt-3 flex items-center gap-3">
                        <button
                          onClick={() =>
                            void confirmPlanUpdate(message.id, message.planProposal as TaskPlan)
                          }
                          disabled={message.planConfirmed || confirmingPlanId === message.id}
                          className="px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                        >
                          {confirmingPlanId === message.id ? "更新中..." : "确认更新学习计划"}
                        </button>
                        {message.planConfirmed && (
                          <span className="text-xs text-emerald-600">已更新</span>
                        )}
                        {message.planError && (
                          <span className="text-xs text-red-600">{message.planError}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {isSending && (
            <div className="flex justify-start">
              <div className="ml-2 bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-2 shadow-sm">
                <div className="flex items-end gap-2">
                  <span
                    className="w-2.5 h-2.5 bg-indigo-500/70 rounded-full"
                    style={{ animation: "typing-bounce 1.1s infinite ease-in-out", animationDelay: "0ms" }}
                  />
                  <span
                    className="w-2.5 h-2.5 bg-indigo-500/70 rounded-full"
                    style={{ animation: "typing-bounce 1.1s infinite ease-in-out", animationDelay: "150ms" }}
                  />
                  <span
                    className="w-2.5 h-2.5 bg-indigo-500/70 rounded-full"
                    style={{ animation: "typing-bounce 1.1s infinite ease-in-out", animationDelay: "300ms" }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* 接受笔记更新按钮 */}
          {showAcceptNoteButton && (
            <div className="flex justify-center py-4">
              <button
                onClick={handleAcceptNoteUpdate}
                disabled={isAcceptingNote}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl"
              >
                <CheckCircle className="w-5 h-5" />
                <span className="font-medium">{isAcceptingNote ? "更新中..." : "接受笔记更新"}</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Chat Input Footer */}
      <div className="bg-white border-t border-gray-200 p-4">
        <div className="max-w-4xl mx-auto">
          {(isPlanActive || isPlanPaused) && (
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-gray-600">
              <span>
                {isPlanPaused ? "计划已挂起，可继续调整或结束计划。" : "当前处于计划调整中，可随时结束计划。"}
              </span>
              {isPlanPaused && (
                <button
                  onClick={() => void handleResumePlan()}
                  disabled={isSending || showIntentDisplay}
                  className="px-2.5 py-1 rounded-full bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  继续调整
                </button>
              )}
              <button
                onClick={() => void handleExitPlan()}
                disabled={isSending || showIntentDisplay}
                className="px-2.5 py-1 rounded-full border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-50"
              >
                结束计划
              </button>
            </div>
          )}
          <div className="flex items-end gap-3 bg-gray-50 rounded-2xl border border-gray-200 p-3 focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
            <textarea
              placeholder={showIntentDisplay ? intentDisplay : (isSending ? "Tutor 思考中..." : "输入你的问题或想法...")}
              rows={1}
              value={inputText}
              onChange={(event) => {
                // 如果有意图识别显示，不允许用户输入
                if (!showIntentDisplay) {
                  setInputText(event.target.value);
                }
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
              disabled={isSending || showIntentDisplay}
              className="flex-1 bg-transparent border-none outline-none px-2 py-2 text-gray-900 placeholder:text-gray-400 resize-none max-h-32"
              style={{ minHeight: '40px' }}
            />
            {isSending ? (
              <button
                onClick={handleStopGeneration}
                className="p-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors flex-shrink-0"
              >
                <Square className="w-5 h-5" />
              </button>
            ) : (
              <button
                onClick={() => void sendMessage()}
                disabled={isSending || !inputText.trim() || showIntentDisplay}
                className="p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>
          <p className="text-xs text-gray-500 text-center mt-2">
            按 Enter 发送，Shift + Enter 换行
          </p>
        </div>
      </div>
    </div>
  );
}
