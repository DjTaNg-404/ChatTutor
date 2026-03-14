import { createBrowserRouter, Navigate } from "react-router";
import { RootLayout } from "./components/RootLayout";
import { TutorSession } from "./components/TutorSession";
import { SettingsPage } from "./components/SettingsPage";
import { ChatHistoryPage } from "./components/ChatHistoryPage";
import { DailyNotePage } from "./components/DailyNotePage";
import { TaskNotePage } from "./components/TaskNotePage";
import { NewTaskPage } from "./components/NewTaskPage";

const TASK_DRAFT_KEY = "task_draft";

function ensureDraftTaskId() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(TASK_DRAFT_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      if (data && typeof data.id === "string") {
        return data.id;
      }
    }
  } catch {
    // ignore
  }

  const id = `task_${Date.now().toString(36)}`;
  try {
    localStorage.setItem(
      TASK_DRAFT_KEY,
      JSON.stringify({ id, title: "新的学习", icon: "✔" })
    );
  } catch {
    // ignore
  }
  return id;
}

function DraftIndex() {
  const draftId = ensureDraftTaskId();
  if (!draftId) {
    return <TutorSession />;
  }
  return <Navigate to={`/task/${draftId}`} replace />;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <DraftIndex /> },
      { path: "task/:taskId", element: <TutorSession /> },
      { path: "task/new", element: <NewTaskPage /> },
    ],
  },
  {
    path: "/settings",
    element: <SettingsPage />,
  },
  {
    path: "/history/:date",
    element: <ChatHistoryPage />,
  },
  {
    path: "/daily-note/:date",
    element: <DailyNotePage />,
  },
  {
    path: "/task-note/:taskId",
    element: <TaskNotePage />,
  },
]);
