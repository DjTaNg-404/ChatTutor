import sys
import os
import time
from langchain_core.messages import HumanMessage

# 将项目根目录添加到 python path，确保能导入 app
sys.path.append(os.getcwd())

from app.core.agent_builder import build_agent
from app.core import context

# 预设的20个连贯问题
QUESTIONS = [
    "你好，我最近想学机器学习，听说有个很火的算法叫“随机森林”，能简单介绍一下它是做什么的吗？",
    "它属于监督学习还是无监督学习？这两者有什么本质区别？",
    "在了解随机森林之前，我是不是需要先懂“决策树”？决策树也是一种算法吗？",
    "能不能用通俗的例子（比如挑西瓜或者相亲）解释一下决策树是怎么工作的？",
    "决策树听起来很直观，那它有什么明显的缺点吗？为什么我们还需要随机森林？",
    "懂了，容易过拟合。那随机森林具体是怎么解决这个过拟合问题的？",
    "你刚才提到了“集成学习”（Ensemble Learning），这个词太专业了，能解释一下吗？",
    "所以在随机森林里，是把很多棵树种在一起吗？这些树是一模一样的吗？",
    "如果不一模一样，那它们是怎么变得“随机”的？",
    "这里有个词叫 Bagging，好像跟抽样有关，能详细展开讲讲它是怎么操作数据的吗？",
    "既然数据是随机抽的，那特征呢？构建每一棵树的时候，也是用所有的特征吗？",
    "为什么要这就做？如果每棵树都只看一部分特征，会不会导致有些树变这“瞎子”，判断很不准？",
    "好了，现在我有一堆树了。如果来了一个新数据，这100棵树有的说是A，有的说是B，最后怎么定夺？",
    "如果是做预测房价（回归问题），而不是分类，它们又是怎么“投票”的呢？",
    "这样看的话，随机森林和那种“梯度提升树”（GBDT/XGBoost）有什么区别？感觉都是很多树啊。",
    "随机森林有什么参数是比较重要的？如果我想调优，主要看哪几个？",
    "说了这么多优点，随机森林有什么缺点或者不适用的场景吗？比如处理稀疏数据的时候？",
    "我不仅想要预测结果，还想知道哪些特征（比如西瓜的纹理、敲击声）对结果最重要，随机森林能告诉我吗？",
    "理论我大概明白了。如果我要在 Python 里用 scikit-learn 来写一个随机森林的分类 demo，代码大概长什么样？",
    "最后总结一下吧，作为一个新人，你觉得我学习随机森林最应该记住的核心理念是什么？"
]

def run_simulation():
    print("🚀 [System] 正在初始化 Agent...")
    graph = build_agent()
    
    # 使用固定的 thread_id 确保是同一场对话
    config = {"configurable": {"thread_id": "sim_test_session_001"}}
    
    print(f"🎬 [System] 开始模拟 20 轮连贯对话测试")
    print(f"📌 [Config] Compression Threshold: {context.COMPRESSION_THRESHOLD}")
    print(f"📌 [Config] Recall Window: Exclude Last {12}")
    
    start_time_all = time.time()
    
    # 核心修复：手动维护客户端状态（Client-side State Management）
    # 在没有 Checkpointer 的情况下，我们需要自己保存整个 state 对象
    # 初始化状态
    current_state = {
        "messages": [],
        "conversation_summary": "",
        "summarized_msg_count": 0
    }
    
    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n{'='*20} 第 {i} 轮: User 发问 {'='*20}")
        print(f"👤 User: {question}")
        
        # 1. 将用户问题追加到当前历史消息中
        # 注意：我们这里模拟一个新的 HumanMessage，追加到 state['messages'] 列表末尾
        # 但在 LangGraph 的 stream 调用中，我们可以直接传整个 updated state
        user_msg = HumanMessage(content=question)
        current_state["messages"].append(user_msg)
        
        # 记录每轮耗时
        t0 = time.time()
        
        # 2. 发送请求
        # 关键点：我们将整个 current_state 喂给 graph
        # stream_mode="values" 会返回每一步的状态更新，我们需要的是最后一步
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
        # 用 graph 返回的最新状态覆盖我们的本地状态
        current_state = final_state
        
        duration = time.time() - t0
        
        # 5. 提取并展示结果
        messages = current_state['messages']
        if not messages:
            print("⚠️ Warning: Empty message list in final state.")
            continue
            
        last_msg = messages[-1]
        
        if isinstance(last_msg, dict):
             # 某些极端情况下可能是 dict，防御性编程
             content = last_msg.get("content", "")
        else:
             content = last_msg.content

        # 只截取前100个字展示，避免刷屏
        preview = content.replace('\n', ' ')
        print(f"🤖 AI ({duration:.1f}s): {preview[:80]}... (Total {len(content)} chars)")
        
        
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
            
        # 这是一个 "Hack" 测试：我们手动跑一遍 recall，看看基于当前的问题，刚才 Agent 可能召回了啥
        # 注意：我们使用当前所有的消息（除了刚生成的这条 AI 回复）作为历史库
        history_for_recall = messages[:-1] 
        simulated_recall = context.retrieve_relevant_messages(
            history_for_recall, 
            question, 
            exclude_last_n=12, # 要和 context.py 里的配置一致
            top_k=2
        )
        
        if simulated_recall:
            print(f"  - ✅ [召回命中] 假如现在提问，会召回以下旧记忆:\n{simulated_recall.strip()[:150]}...")
        else:
            print(f"  - ⭕ [无召回] 本轮未命中旧历史 (属正常，如无相关旧话)")
            
    print(f"\n{'='*10} 测试结束 (总耗时: {time.time() - start_time_all:.1f}s) {'='*10}")

if __name__ == "__main__":
    run_simulation()
