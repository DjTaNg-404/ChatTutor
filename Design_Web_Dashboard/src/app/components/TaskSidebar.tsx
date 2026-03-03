import { Link, useLocation, useNavigate } from "react-router";
import { Plus, ChevronDown, ChevronRight, BookOpen, Settings, Archive } from "lucide-react";
import { useState } from "react";

interface Task {
  id: string;
  title: string;
  icon: string;
  status: "active" | "archived";
}

const activeTasks: Task[] = [
  { id: "1", title: "掌握随机森林算法", icon: "🌳", status: "active" },
  { id: "2", title: "雅思口语备考", icon: "🗣️", status: "active" },
  { id: "3", title: "React Hooks 深入", icon: "⚛️", status: "active" },
  { id: "4", title: "机器学习数学基础", icon: "📊", status: "active" },
];

const archivedTasks: Task[] = [
  { id: "5", title: "Python 基础语法", icon: "🐍", status: "archived" },
  { id: "6", title: "SQL 查询优化", icon: "💾", status: "archived" },
];

export function TaskSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [showArchived, setShowArchived] = useState(false);

  const isTaskActive = (taskId: string) => {
    return location.pathname === `/task/${taskId}`;
  };

  return (
    <aside className="w-[250px] bg-white border-r border-gray-200 flex flex-col">
      {/* Brand Logo */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-blue-600 rounded-lg flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900">ChatTutor</h1>
        </div>
      </div>

      {/* New Task Button */}
      <div className="p-4 border-b border-gray-200">
        <button className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium">
          <Plus className="w-5 h-5" />
          新建学习任务
        </button>
      </div>

      {/* Active Learning Tasks */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-2 mb-2">
            进行中的任务
          </h3>
          <div className="space-y-1">
            {activeTasks.map((task) => (
              <Link
                key={task.id}
                to={`/task/${task.id}`}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  isTaskActive(task.id)
                    ? "bg-indigo-50 text-indigo-600 shadow-sm"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <span className="text-lg">{task.icon}</span>
                <span className="flex-1 text-sm font-medium truncate">
                  {task.title}
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Archived Tasks */}
        <div className="p-4 border-t border-gray-200">
          <button
            onClick={() => setShowArchived(!showArchived)}
            className="w-full flex items-center gap-2 px-2 py-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <Archive className="w-4 h-4" />
            <span className="flex-1 text-left text-xs font-semibold uppercase tracking-wider">
              已归档任务
            </span>
            {showArchived ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
          {showArchived && (
            <div className="mt-2 space-y-1">
              {archivedTasks.map((task) => (
                <Link
                  key={task.id}
                  to={`/task/${task.id}`}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
                >
                  <span className="text-lg opacity-60">{task.icon}</span>
                  <span className="flex-1 text-sm truncate">{task.title}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom System Settings */}
      <div className="border-t border-gray-200 p-4">
        <Link
          to="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
        >
          <Settings className="w-5 h-5 text-gray-500" />
          <span className="text-sm font-medium">系统设置</span>
        </Link>
      </div>
    </aside>
  );
}
