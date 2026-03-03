import { useParams, useNavigate } from "react-router";
import { ArrowLeft, Calendar, Edit3, Save, Sparkles } from "lucide-react";

interface DailyNote {
  date: string;
  taskTitle: string;
  aiSummary: {
    keyLearnings: string[];
    reviewAreas: string[];
    achievements: string[];
  };
  userNotes: string;
}

// 模拟每日笔记数据
const dailyNotesData: { [key: string]: DailyNote } = {
  "2026-03-02": {
    date: "2026-03-02",
    taskTitle: "掌握随机森林算法",
    aiSummary: {
      keyLearnings: [
        "理解随机森林的集成学习原理，包括 Bootstrap 采样和特征随机性",
        "掌握特征重要性的计算方法（基于不纯度降低）",
        "学习超参数调优的关键参数和网格搜索方法",
        "对比随机森林与其他算法的优缺点",
      ],
      reviewAreas: [
        "过拟合问题的解决方案需要实践加深理解",
        "交叉验证的具体实现细节",
        "特征工程与随机森林结合的最佳实践",
      ],
      achievements: [
        "完成了随机森林核心概念的学习",
        "理解了特征重要性评估的原理",
        "掌握了基本的超参数调优方法",
      ],
    },
    userNotes: "今天的学习非常充实，特别是特征重要性的部分讲解很清楚。明天需要找一个实际数据集练习，加深对超参数调优的理解。\n\n重点记录：\n- n_estimators 建议从100开始\n- max_depth 通常在10-20之间\n- 使用 GridSearchCV 进行参数搜索\n\n下一步计划：\n1. 使用 Kaggle 的泰坦尼克数据集练习\n2. 对比随机森林和 XGBoost 的效果\n3. 学习特征工程技巧",
  },
  "2026-03-01": {
    date: "2026-03-01",
    taskTitle: "掌握随机森林算法",
    aiSummary: {
      keyLearnings: [
        "复习了决策树的基本构建流程",
        "理解了信息增益与基尼系数的计算方法",
        "学习了 CART 算法的实现原理",
      ],
      reviewAreas: [
        "特征选择的优化策略",
        "决策树剪枝的具体方法",
      ],
      achievements: [
        "巩固了决策树基础知识",
        "为学习随机森林打下了良好基础",
      ],
    },
    userNotes: "复习了决策树的核心概念，为明天学习随机森林做准备。信息熵的计算需要多练习。",
  },
};

export function DailyNotePage() {
  const { date } = useParams<{ date: string }>();
  const navigate = useNavigate();

  const noteData = date ? dailyNotesData[date] : null;

  // 格式化日期显示
  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    const [year, month, day] = dateStr.split("-");
    return `${year}年${month}月${day}日`;
  };

  if (!noteData) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Edit3 className="w-8 h-8 text-gray-400" />
          </div>
          <p className="text-gray-500">暂无此日期的学习笔记</p>
          <button
            onClick={() => navigate(-1)}
            className="mt-4 text-indigo-600 hover:text-indigo-700 text-sm font-medium"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto">
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
                  <Edit3 className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <h1 className="text-2xl font-semibold text-gray-900">
                    {noteData.taskTitle} - 学习笔记
                  </h1>
                  <p className="text-sm text-gray-600 mt-0.5">
                    {formatDate(noteData.date)}
                  </p>
                </div>
              </div>
            </div>

            <button className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">
              <Save className="w-4 h-4" />
              <span className="text-sm font-medium">保存笔记</span>
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* AI Generated Summary */}
          <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl border border-indigo-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-indigo-600" />
              <h2 className="text-lg font-semibold text-gray-900">AI 学习总结</h2>
              <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-medium ml-2">
                自动生成
              </span>
            </div>

            {/* Key Learnings */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                📚 今日学习要点
              </h3>
              <ul className="space-y-2">
                {noteData.aiSummary.keyLearnings.map((learning, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-sm text-gray-700 bg-white rounded-lg p-3"
                  >
                    <span className="text-indigo-600 font-semibold mt-0.5">
                      {idx + 1}.
                    </span>
                    <span className="flex-1">{learning}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Achievements */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                ✨ 学习成果
              </h3>
              <ul className="space-y-2">
                {noteData.aiSummary.achievements.map((achievement, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-sm text-gray-700 bg-white rounded-lg p-3"
                  >
                    <span className="text-green-500 mt-0.5">✓</span>
                    <span className="flex-1">{achievement}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Review Areas */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                🔄 待复习内容
              </h3>
              <ul className="space-y-2">
                {noteData.aiSummary.reviewAreas.map((area, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-sm text-amber-700 bg-white rounded-lg p-3"
                  >
                    <span className="text-amber-500 mt-0.5">⚠</span>
                    <span className="flex-1">{area}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* User Notes */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">我的笔记</h2>
              <button className="text-sm text-gray-500 hover:text-gray-700 transition-colors">
                编辑
              </button>
            </div>

            <textarea
              defaultValue={noteData.userNotes}
              rows={12}
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 outline-none resize-none font-mono text-sm text-gray-700"
              placeholder="在这里添加你的个人学习笔记、心得体会或问题..."
            />

            <p className="text-xs text-gray-500 mt-2">
              支持 Markdown 格式 · 自动保存
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center justify-between bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Calendar className="w-4 h-4" />
              <span>最后编辑：今天 14:32</span>
            </div>
            <div className="flex items-center gap-3">
              <button className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
                导出为 PDF
              </button>
              <button className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
                分享笔记
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
