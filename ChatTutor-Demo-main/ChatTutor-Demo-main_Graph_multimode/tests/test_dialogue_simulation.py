"""
对话测试模拟脚本
基于 test_simulation.py 改写，使用 questions_complete.json 作为数据源

功能：
1. 从 questions_complete.json 加载所有问题
2. 初始化 ChatTutor Agent (使用 agent_builder_v6)
3. 模拟多轮对话，每轮提问并获取AI回复
4. 每5轮自动保存对话记忆到 memory/sessions 文件夹
5. 最终保存完整的对话记忆

使用方法：
1. 确保已安装所有依赖: pip install -r requirements.txt
2. 确保已配置 DEEPSEEK_API_KEY 环境变量
3. 在项目根目录运行: python tests/test_dialogue_simulation.py

输出：
- 对话过程会显示在控制台
- 记忆文件保存到: memory/sessions/{session_id}.json
"""

import sys
import os
import time
import json
from langchain_core.messages import HumanMessage

# 将项目根目录添加到 python path，确保能导入 app
sys.path.append(os.getcwd())

from chattutor.core.agent_builder_v6 import build_agent
from chattutor.core import memory
from chattutor.core import context

def load_questions_from_json(json_path):
    """从JSON文件加载问题，并扁平化为一个列表"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {json_path}")
        # 尝试使用绝对路径
        abs_path = os.path.abspath(json_path)
        print(f"📁 尝试绝对路径: {abs_path}")
        if os.path.exists(abs_path):
            with open(abs_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            raise

    # 扁平化所有问题到一个列表中
    all_questions = []
    for item in data:
        if isinstance(item, dict) and "questions" in item:
            all_questions.extend(item["questions"])
        else:
            # 如果是其他格式，直接添加
            all_questions.append(item)

    print(f"📊 从 {json_path} 加载了 {len(all_questions)} 个问题")
    return all_questions

def run_simulation():
    # 确保 memory 目录存在
    os.makedirs("memory/sessions", exist_ok=True)
    os.makedirs("memory/notes", exist_ok=True)

    print("🚀 [System] 正在初始化 Agent...")
    graph = build_agent()

    # 加载问题数据 - 使用相对于脚本的路径
    script_dir = os.path.dirname(__file__)
    json_path = os.path.join(script_dir, "questions_complete.json")
    questions = load_questions_from_json(json_path)

    # 使用固定的 thread_id 确保是同一场对话
    session_id = f"dialogue_simulation_{int(time.time())}"
    config = {"configurable": {"thread_id": session_id}}

    print(f"🎬 [System] 开始模拟 {len(questions)} 轮对话测试")
    print(f"📌 [System] 会话ID: {session_id}")
    print(f"📌 [Config] Compression Threshold: {context.COMPRESSION_THRESHOLD}")
    print(f"📌 [Config] Recall Window: Exclude Last {12}")

    start_time_all = time.time()

    # 初始化状态 - 需要包含 memory.save_session 所需的字段
    current_state = {
        "messages": [],
        "session_id": session_id,
        "user_id": "test_user",
        "current_topic": "随机森林教学",
        "conversation_summary": "",
        "summarized_msg_count": 0,
        "plan": None,
        "should_exit": False,
        "tutor_output": None,
        "judge_output": None,
        "inquiry_output": None,
        "summary_output": None,
        "last_intent": None
    }

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*20} 第 {i} 轮: User 发问 {'='*20}")
        print(f"👤 User: {question}")

        # 1. 将用户问题追加到当前历史消息中
        user_msg = HumanMessage(content=question)
        current_state["messages"].append(user_msg)

        # 记录每轮耗时
        t0 = time.time()

        # 2. 发送请求
        events = list(graph.stream(
            current_state,
            config,
            stream_mode="values"
        ))

        # 3. 捕获最终状态
        if not events:
            print("⚠️ Error: No events returned from graph stream.")
            continue

        final_state = events[-1]

        # 4. 更新客户端持有的状态，以便下一轮使用
        current_state = final_state

        duration = time.time() - t0

        # 5. 提取并展示结果
        messages = current_state['messages']
        if not messages:
            print("⚠️ Warning: Empty message list in final state.")
            continue

        last_msg = messages[-1]

        if isinstance(last_msg, dict):
             content = last_msg.get("content", "")
        else:
             content = last_msg.content

        # 只截取前100个字展示，避免刷屏
        preview = content.replace('\n', ' ')
        print(f"🤖 AI ({duration:.1f}s): {preview[:80]}... (Total {len(content)} chars)")

        # 每5轮保存一次对话记忆
        if i % 5 == 0 or i == len(questions):
            try:
                saved_path = memory.save_session(current_state)
                print(f"💾 已保存对话记忆到: {saved_path}")
            except Exception as e:
                print(f"⚠️ 保存记忆失败: {e}")

        # --- 深度探查 Agent 内部状态 (Introspection) ---
        summary = current_state.get("conversation_summary", "")
        cursor = current_state.get("summarized_msg_count", 0)

        print(f"\n🔍 [Context 探针]")
        print(f"  - 历史总消息数: {len(messages)}")
        print(f"  - 已压缩游标: {cursor}")

        if summary:
            print(f"  - 当前认知链摘要 ({len(summary)} chars): {summary[:40]}...")
        else:
            print(f"  - 当前认知链摘要: (暂无)")

        # 模拟 recall 测试
        history_for_recall = messages[:-1]
        simulated_recall = context.retrieve_relevant_messages(
            history_for_recall,
            question,
            exclude_last_n=12,
            top_k=2
        )

        if simulated_recall:
            print(f"  - ✅ [召回命中] 假如现在提问，会召回以下旧记忆:\n{simulated_recall.strip()[:150]}...")
        else:
            print(f"  - ⭕ [无召回] 本轮未命中旧历史 (属正常，如无相关旧话)")

    print(f"\n{'='*10} 测试结束 (总耗时: {time.time() - start_time_all:.1f}s) {'='*10}")

    # 最终保存完整的对话记忆
    try:
        final_path = memory.save_session(current_state)
        print(f"💾 最终对话记忆已保存到: {final_path}")
    except Exception as e:
        print(f"⚠️ 最终保存记忆失败: {e}")

if __name__ == "__main__":
    run_simulation()