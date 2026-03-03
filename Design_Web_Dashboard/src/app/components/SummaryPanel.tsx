import { Calendar, Edit3, ExternalLink } from "lucide-react";
import { Link } from "react-router";

interface DailySummary {
  id: string;
  date: string;
  displayDate: string;
  keyLearnings: string[];
  reviewAreas: string[];
}

const dailySummaries: DailySummary[] = [
  {
    id: "1",
    date: "2026-03-02",
    displayDate: "3月2日",
    keyLearnings: [
      "理解随机森林的集成学习原理",
      "掌握特征重要性评估方法",
      "学习决策树的剪枝技术",
    ],
    reviewAreas: ["过拟合问题的解决方案", "交叉验证的实践应用"],
  },
  {
    id: "2",
    date: "2026-03-01",
    displayDate: "3月1日",
    keyLearnings: [
      "复习决策树的基本构建流程",
      "理解信息增益与基尼系数",
      "实践 CART 算法实现",
    ],
    reviewAreas: ["特征选择的优化策略"],
  },
  {
    id: "3",
    date: "2026-02-29",
    displayDate: "2月29日",
    keyLearnings: [
      "学习 Bagging 集成方法",
      "理解 Bootstrap 采样原理",
      "对比随机森林与 GBDT",
    ],
    reviewAreas: ["模型参数调优技巧", "树的深度控制"],
  },
  {
    id: "4",
    date: "2026-02-28",
    displayDate: "2月28日",
    keyLearnings: [
      "掌握特征工程基础",
      "实践缺失值处理方法",
    ],
    reviewAreas: ["类别特征编码方式"],
  },
];

export function SummaryPanel() {
  return (
    <aside className="w-[300px] bg-white border-l border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">学习时间线</h2>
        <p className="text-sm text-gray-600 mt-1">每日学习总结</p>
      </div>

      {/* Timeline Body */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="relative">
          {/* Vertical Line */}
          <div className="absolute left-4 top-3 bottom-3 w-px bg-gradient-to-b from-indigo-200 via-indigo-200 to-transparent"></div>

          {/* Summary Cards */}
          <div className="space-y-6">
            {dailySummaries.map((summary, index) => (
              <div key={summary.id} className="relative pl-10">
                {/* Timeline Dot */}
                <div
                  className={`absolute left-0 top-1.5 w-8 h-8 rounded-full flex items-center justify-center ${
                    index === 0
                      ? "bg-indigo-600 shadow-lg shadow-indigo-200"
                      : "bg-indigo-100"
                  }`}
                >
                  <Calendar
                    className={`w-4 h-4 ${
                      index === 0 ? "text-white" : "text-indigo-600"
                    }`}
                  />
                </div>

                {/* Card */}
                <div
                  className={`bg-white rounded-xl border p-4 hover:shadow-md transition-all ${
                    index === 0
                      ? "border-indigo-200 shadow-sm"
                      : "border-gray-200"
                  }`}
                >
                  {/* Date Header */}
                  <div className="flex items-center justify-between mb-3">
                    <h3
                      className={`font-semibold ${
                        index === 0 ? "text-indigo-600" : "text-gray-900"
                      }`}
                    >
                      {summary.displayDate}
                    </h3>
                    {index === 0 && (
                      <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-medium">
                        今天
                      </span>
                    )}
                  </div>

                  {/* Key Learnings */}
                  <div className="mb-3">
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                      关键学习点
                    </h4>
                    <ul className="space-y-1.5">
                      {summary.keyLearnings.map((learning, idx) => (
                        <li
                          key={idx}
                          className="text-sm text-gray-700 flex items-start gap-2"
                        >
                          <span className="text-indigo-500 mt-1">•</span>
                          <span className="flex-1">{learning}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Review Areas */}
                  {summary.reviewAreas.length > 0 && (
                    <div className="mb-3">
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                        待复习
                      </h4>
                      <ul className="space-y-1.5">
                        {summary.reviewAreas.map((area, idx) => (
                          <li
                            key={idx}
                            className="text-sm text-amber-700 flex items-start gap-2"
                          >
                            <span className="text-amber-500 mt-1">•</span>
                            <span className="flex-1">{area}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* View Full Chat Log */}
                  <div className="flex items-center gap-2 mt-2">
                    <Link
                      to={`/history/${summary.date}`}
                      className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      <span>查看完整对话记录</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                    <span className="text-gray-300">|</span>
                    <Link
                      to={`/daily-note/${summary.date}`}
                      className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-700 font-medium"
                    >
                      <Edit3 className="w-3 h-3" />
                      <span>笔记</span>
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}