import { Outlet, useLocation } from "react-router";
import { TaskSidebar } from "./TaskSidebar";
import { SummaryPanel } from "./SummaryPanel";
import { useState } from "react";

export function RootLayout() {
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const location = useLocation();
  const hideSummaryPanel = location.pathname.startsWith("/task/new");

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left Sidebar */}
      <TaskSidebar />

      {/* Middle Content Area */}
      <main className="flex-1 overflow-hidden">
        <Outlet context={{ isPanelOpen, setIsPanelOpen }} />
      </main>

      {/* Right Summary Panel */}
      {isPanelOpen && !hideSummaryPanel && <SummaryPanel />}
    </div>
  );
}
