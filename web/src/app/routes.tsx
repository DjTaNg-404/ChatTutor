import { createBrowserRouter } from "react-router";
import { RootLayout } from "./components/RootLayout";
import { TutorSession } from "./components/TutorSession";
import { SettingsPage } from "./components/SettingsPage";
import { ChatHistoryPage } from "./components/ChatHistoryPage";
import { DailyNotePage } from "./components/DailyNotePage";
import { TaskNotePage } from "./components/TaskNotePage";
import { NewTaskPage } from "./components/NewTaskPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <TutorSession /> },
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