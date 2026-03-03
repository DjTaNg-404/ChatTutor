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

// 模拟不同日期的对话记录
const chatHistoryData: { [key: string]: ChatMessage[] } = {
  "2026-03-02": [
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
    {
      id: "5",
      role: "assistant",
      content: `特征重要性的计算主要基于每个特征在决策树中的贡献度。有两种常见方法：

## 基于不纯度的重要性（Gini Importance）

当一个特征被用于分裂节点时，它会降低节点的不纯度。特征重要性就是该特征在所有树中带来的平均不纯度降低量。

计算公式：
- 对每棵树，计算该特征带来的不纯度减少
- 对所有树求平均
- 归一化使所有特征重要性总和为1

\`\`\`python
# 获取特征重要性
importances = rf.feature_importances_
feature_names = ['特征1', '特征2', '特征3']

for name, importance in zip(feature_names, importances):
    print(f'{name}: {importance:.4f}')
\`\`\`

## 优势

1. 自动评估特征相关性
2. 可以用于特征选择
3. 帮助理解模型决策依据

你想深入了解某个方面吗？`,
      timestamp: "10:37",
    },
    {
      id: "6",
      role: "user",
      content: "这个解释很清楚！我想知道在实际项目中，如何选择合适的超参数？",
      timestamp: "10:40",
    },
    {
      id: "7",
      role: "assistant",
      content: `超参数调优是机器学习项目中的关键步骤。对于随机森林，主要关注以下参数：

## 关键超参数

### 1. n_estimators（树的数量）
- **建议**：从100开始，逐步增加到500-1000
- **影响**：更多树通常效果更好，但计算成本增加
- **经验**：性能提升会逐渐放缓

### 2. max_depth（树的最大深度）
- **建议**：根据数据复杂度调整
- **风险**：太深容易过拟合，太浅欠拟合
- **常用值**：10-20

### 3. min_samples_split（分裂所需最小样本数）
- **建议**：2-10之间
- **作用**：控制过拟合

### 4. max_features（每次分裂考虑的特征数）
- **分类**：sqrt(n_features)
- **回归**：n_features/3

## 调优方法

\`\`\`python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [10, 20, 30],
    'min_samples_split': [2, 5, 10]
}

grid_search = GridSearchCV(
    RandomForestClassifier(),
    param_grid,
    cv=5,  # 5折交叉验证
    scoring='accuracy'
)

grid_search.fit(X_train, y_train)
print(f'最佳参数: {grid_search.best_params_}')
\`\`\`

建议使用交叉验证来评估不同参数组合的效果。`,
      timestamp: "10:43",
    },
    {
      id: "8",
      role: "user",
      content: "非常有帮助！最后一个问题，随机森林相比其他算法有什么优缺点？",
      timestamp: "10:46",
    },
    {
      id: "9",
      role: "assistant",
      content: `让我总结一下随机森林的优缺点，这样你可以在实际项目中做出更好的选择。

## ✅ 优点

1. **高准确性**
   - 集成学习效果好
   - 适用于分类和回归

2. **鲁棒性强**
   - 对异常值和噪声不敏感
   - 不需要特征归一化

3. **自动特征选择**
   - 提供特征重要性
   - 可处理高维数据

4. **易于使用**
   - 参数调优相对简单
   - 不容易过拟合

5. **并行化**
   - 树的训练可以并行
   - 训练速度快

## ❌ 缺点

1. **模型解释性差**
   - 黑盒模型
   - 难以可视化和解释

2. **内存消耗大**
   - 需要存储多棵树
   - 大数据集可能有问题

3. **预测速度慢**
   - 需要遍历所有树
   - 实时预测可能受限

4. **外推能力弱**
   - 无法预测超出训练数据范围的值
   - 对时序数据效果可能不佳

## 对比其他算法

| 算法 | 准确性 | 速度 | 解释性 | 适用场景 |
|------|--------|------|--------|----------|
| 随机森林 | 高 | 中 | 低 | 通用，结构化数据 |
| XGBoost | 很高 | 快 | 低 | 竞赛，大数据 |
| 决策树 | 中 | 快 | 高 | 需要解释性 |
| 逻辑回归 | 中 | 很快 | 高 | 简单分类 |

今天的学习很充实！你对随机森林有了全面的理解了吗？`,
      timestamp: "10:49",
    },
    {
      id: "10",
      role: "user",
      content: "完全理解了！谢谢你的详细讲解，今天学到了很多。",
      timestamp: "10:51",
    },
    {
      id: "11",
      role: "assistant",
      content: "太好了！你今天的学习表现很棒。我们深入探讨了随机森林的原理、特征重要性、超参数调优和优缺点对比。建议你接下来可以找一个实际数据集练习一下，加深理解。继续保持这样的学习热情！",
      timestamp: "10:52",
    },
  ],
  "2026-03-01": [
    {
      id: "1",
      role: "assistant",
      content: "早上好！今天我们来复习决策树的基本构建流程。你还记得决策树是如何选择分裂特征的吗？",
      timestamp: "09:15",
    },
    {
      id: "2",
      role: "user",
      content: "我记得是通过信息增益或基尼系数来选择，但具体怎么计算有些模糊。",
      timestamp: "09:17",
    },
    {
      id: "3",
      role: "assistant",
      content: `很好！让我帮你复习一下这两个重要概念。

## 信息增益（Information Gain）

基于信息熵的概念：

\`\`\`python
import numpy as np

def entropy(y):
    """计算熵"""
    _, counts = np.unique(y, return_counts=True)
    probs = counts / len(y)
    return -np.sum(probs * np.log2(probs))

def information_gain(X, y, feature):
    """计算信息增益"""
    parent_entropy = entropy(y)
    
    # 计算分裂后的加权熵
    values = np.unique(X[:, feature])
    weighted_entropy = 0
    
    for value in values:
        subset = y[X[:, feature] == value]
        weight = len(subset) / len(y)
        weighted_entropy += weight * entropy(subset)
    
    return parent_entropy - weighted_entropy
\`\`\`

## 基尼系数（Gini Index）

衡量节点的不纯度：

Gini = 1 - Σ(pi²)

其中 pi 是类别 i 的概率。

基尼系数越小，节点越纯。`,
      timestamp: "09:19",
    },
  ],
};

const dateTitles: { [key: string]: string } = {
  "2026-03-02": "掌握随机森林算法",
  "2026-03-01": "决策树基础复习",
  "2026-02-29": "集成学习方法",
  "2026-02-28": "特征工程实践",
};

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
            setTaskTitle(dateTitles[date] || "学习记录");
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
          setTaskTitle(historyResponses[0]?.data.topic || dateTitles[date] || "学习记录");
          setMessages(mergedMessages);
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "读取历史记录失败";
          setErrorText(message);
          setMessages([]);
          setTaskTitle(dateTitles[date] || "学习记录");
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
