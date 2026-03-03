import { useParams, useOutletContext } from "react-router";
import { Send, CheckCircle, PanelRightClose, PanelRightOpen, BookOpen } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface OutletContext {
  isPanelOpen: boolean;
  setIsPanelOpen: (open: boolean) => void;
}

const mockMessages: Message[] = [
  {
    id: "1",
    role: "assistant",
    content: "你好！我是你的 AI 导师。今天我们继续学习随机森林算法。你准备好了吗？有什么问题想要先了解的？",
    timestamp: "10:30",
  },
  {
    id: "2",
    role: "user",
    content: "我想深入理解随机森林是如何通过集成多个决策树来提高预测准确性的。",
    timestamp: "10:32",
  },
  {
    id: "3",
    role: "assistant",
    content: `很好的问题！随机森林的核心思想是**集成学习（Ensemble Learning）**。让我详细解释：

## 基本原理

1. **Bootstrap 采样**
   - 从原始数据集中有放回地随机抽取样本
   - 每棵树使用不同的训练子集
   
2. **特征随机性**
   - 每次分裂节点时，只考虑随机选择的特征子集
   - 增加树之间的多样性
   
3. **投票机制**
   - 分类问题：多数投票
   - 回归问题：平均预测值

\`\`\`python
from sklearn.ensemble import RandomForestClassifier

# 创建随机森林模型
rf = RandomForestClassifier(
    n_estimators=100,  # 树的数量
    max_depth=10,
    min_samples_split=2
)
\`\`\`

这种方法减少了过拟合，提高了泛化能力。你理解了吗？`,
    timestamp: "10:33",
  },
  {
    id: "4",
    role: "user",
    content: "理解了！那么特征重要性是如何计算的呢？",
    timestamp: "10:35",
  },
];

const taskTitles: { [key: string]: string } = {
  "1": "掌握随机森林算法",
  "2": "雅思口语备考",
  "3": "React Hooks 深入",
  "4": "机器学习数学基础",
};

export function TutorSession() {
  const { taskId } = useParams();
  const context = useOutletContext<OutletContext>();
  const [messages] = useState<Message[]>(mockMessages);

  // Provide default values if context is undefined
  const isPanelOpen = context?.isPanelOpen ?? true;
  const setIsPanelOpen = context?.setIsPanelOpen ?? (() => {});

  const taskTitle = taskId ? taskTitles[taskId] || "学习任务" : "欢迎使用 ChatTutor";
  const currentDate = "2026年3月2日 星期一";

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
            <button className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium">
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
          {messages.map((message) => (
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
                    
                    // Handle lists
                    if (paragraph.includes('\n   - ') || paragraph.includes('\n1. ')) {
                      const items = paragraph.split('\n').filter(line => line.trim());
                      return (
                        <ul key={idx} className="space-y-1 my-2">
                          {items.map((item, i) => {
                            const cleaned = item.replace(/^[\s\-\d.]+/, '').trim();
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
          ))}
        </div>
      </div>

      {/* Chat Input Footer */}
      <div className="bg-white border-t border-gray-200 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-end gap-3 bg-gray-50 rounded-2xl border border-gray-200 p-3 focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
            <textarea
              placeholder="输入你的问题或想法..."
              rows={1}
              className="flex-1 bg-transparent border-none outline-none px-2 py-2 text-gray-900 placeholder:text-gray-500 resize-none max-h-32"
              style={{ minHeight: '40px' }}
            />
            <button className="p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors flex-shrink-0">
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