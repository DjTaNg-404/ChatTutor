import streamlit as st
import sys
import os
import uuid
import datetime
from langchain_core.messages import HumanMessage, AIMessage
from chattutor.core import memory
from chattutor.core.kg_pipeline import build_knowledge_graph_from_sessions
from chattutor.core import profile_store
from chattutor.core import learning_profile

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# NOTE: Moved import down to avoid crashing if env vars are missing at startup
# from chattutor.core.agent_builder_v2 import build_agent 

# --- Streamlit Config ---
st.set_page_config(page_title="ChatTutor", page_icon="🎓")

# Hide default menu
hide_menu_style = """
        <style>
        #MainMenu {visibility: hidden;}
        /* 调整侧边栏宽度 */
        section[data-testid="stSidebar"] > div {
            width: 350px !important; /* 默认是300px */
            min-width: 350px !important;
        }
        /* 调整expander宽度 */
        .streamlit-expander {
            width: 100% !important;
            max-width: 100% !important;
        }
        /* 调整expander内部内容区域 */
        .streamlit-expanderContent {
            width: 100% !important;
            max-width: 100% !important;
        }
        /* 调整view session窗口中的消息显示 */
        .streamlit-expanderContent div {
            max-width: 100% !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
        }
        </style>
        """
st.markdown(hide_menu_style, unsafe_allow_html=True)

st.title("🎓 ChatTutor AI")

# --- Initialization ---

@st.cache_resource
def get_graph():
    """Builds and caches the LangGraph agent.

    This helper verifies the DEEPSEEK_API_KEY before constructing the
    agent.  Errors are propagated so that Streamlit does not cache an invalid
    result.  If the key is correct, we lazily import the builder and return
    a compiled graph instance (must not be None).
    """
    # Check for API Key first to give a friendly error
    from chattutor.core.config import settings
    key = settings.DEEPSEEK_API_KEY
    if not key or (key.startswith("sk-") and "your" in key.lower()):
        raise ValueError(
            "DEEPSEEK_API_KEY not configured. "
            "Please set the DEEPSEEK_API_KEY environment variable."
        )

    # Lazy import to avoid top-level crash if dependencies missing
    from chattutor.core.agent_builder_v6 import build_agent
    agent = build_agent()
    if agent is None:
        raise RuntimeError("Agent builder returned None")
    return agent

try:
    graph = get_graph()
    if graph is None:
        raise RuntimeError("Graph initialization returned None")
except Exception as e:
    st.error(f"❌ 初始化失败: {e}")
    st.info("请在 ModelScope 创空间的「设置 -> 环境变量」中配置 DEEPSEEK_API_KEY。")
    st.stop()

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:4]}"

if "user_id" not in st.session_state:
    st.session_state.user_id = st.session_state.session_id

if "agent_state_context" not in st.session_state:
    # storing persistent context parts of AgentState
    st.session_state.agent_state_context = {
        "current_topic": "General Knowledge",
        "conversation_summary": None,
        "summarized_msg_count": 0
    }

# --- Knowledge Graph Helper ---


# --- Sidebar ---
with st.sidebar:
    st.header("Debug Info")
    st.text_input("User ID", key="user_id")
    st.write(f"**Session ID:** {st.session_state.session_id}")

    # 用户类型设置
    st.subheader("用户类型设置")

    # 加载当前用户的档案
    current_user_id = st.session_state.user_id
    profile = profile_store.load_profile(current_user_id)
    current_user_type = profile.get("user_type")

    # 显示当前用户类型
    if current_user_type:
        type_map = {
            "primary_school": "小学生",
            "middle_school": "中学生",
            "university": "大学生",
            "adult": "成人学习者"
        }
        current_display = type_map.get(current_user_type, "未设置")
        st.write(f"当前类型: **{current_display}**")
    else:
        st.write("当前类型: **未设置**")

    # 用户类型选择
    user_type_options = {
        "请选择用户类型...": None,
        "小学生": "primary_school",
        "中学生": "middle_school",
        "大学生": "university",
        "成人学习者": "adult"
    }

    selected_display = st.selectbox(
        "选择您的用户类型",
        options=list(user_type_options.keys()),
        help="选择适合您的用户类型，系统将调整教学语气风格"
    )

    selected_type = user_type_options[selected_display]

    if selected_type and selected_type != current_user_type:
        if st.button("更新用户类型", use_container_width=True):
            try:
                # 更新用户档案中的用户类型
                profile = learning_profile.set_user_type(profile, selected_type)
                profile_store.save_profile(profile)
                st.success(f"用户类型已更新！")
                st.rerun()
            except Exception as e:
                st.error(f"更新失败: {e}")

    st.divider()


    # ----------------- Knowledge Graph Visualization -----------------
    with st.expander("Knowledge Graph Visualization"):
        st.write("基于对话记忆构建实体-关系知识图谱并可视化")

        # 模型选择
        model_choice = st.selectbox(
            "选择NER模型",
            options=["bert-base-chinese", "ckiplab/bert-base-chinese-ner", "hfl/chinese-roberta-wwm-ext"],
            index=0,
            help="选择用于命名实体识别的预训练模型"
        )

        # 输出目录设置
        output_dir = st.text_input("输出目录", value="./kg_output", help="知识图谱输出目录（HTML和JSON文件将保存在此）")

        # 构建按钮
        if st.button("🚀 构建知识图谱", use_container_width=True):
            with st.spinner("正在构建知识图谱..."):
                try:
                    kg_log = build_knowledge_graph_from_sessions(
                        sessions_dir="memory/sessions",
                        output_dir=output_dir,
                        model_name=model_choice
                    )

                    st.text_area("构建日志", kg_log, height=300)

                    # 检查是否生成了可视化文件
                    html_files = []
                    json_files = []
                    if os.path.exists(output_dir):
                        for file in os.listdir(output_dir):
                            if file.endswith(".html"):
                                html_files.append(os.path.join(output_dir, file))
                            elif file.endswith(".json"):
                                json_files.append(os.path.join(output_dir, file))

                    if html_files:
                        st.success(f"✅ 生成了 {len(html_files)} 个可视化文件")

                        # 显示最近生成的可视化文件
                        latest_html = max(html_files, key=os.path.getmtime)
                        st.write(f"**最近的可视化文件:** {os.path.basename(latest_html)}")

                        # 嵌入HTML可视化
                        try:
                            with open(latest_html, 'r', encoding='utf-8') as f:
                                html_content = f.read()

                            # 使用Streamlit组件嵌入HTML
                            st.components.v1.html(html_content, height=600, scrolling=True)

                            # 提供下载链接
                            st.download_button(
                                label="📥 下载HTML文件",
                                data=html_content,
                                file_name=os.path.basename(latest_html),
                                mime="text/html"
                            )

                        except Exception as e:
                            st.error(f"加载可视化文件失败: {e}")
                            st.info(f"文件位置: {latest_html}")

                    # 隐藏生成的数据文件部分
                    # if json_files:
                    #     st.write(f"**生成的数据文件:**")
                    #     for json_file in json_files:
                    #         st.write(f"- {os.path.basename(json_file)}")
                    #
                    #     # 显示JSON数据预览
                    #     if json_files:
                    #         latest_json = max(json_files, key=os.path.getmtime)
                    #         try:
                    #             import json as json_module
                    #             with open(latest_json, 'r', encoding='utf-8') as f:
                    #                 json_data = json_module.load(f)
                    #
                    #             with st.expander("查看数据统计"):
                    #                 st.json({
                    #                     "nodes": len(json_data.get("nodes", [])),
                    #                     "edges": len(json_data.get("edges", [])),
                    #                     "metadata": json_data.get("metadata", {})
                    #                 })
                    #
                    #             st.download_button(
                    #                 label="📥 下载JSON数据",
                    #                 data=json_module.dumps(json_data, ensure_ascii=False, indent=2),
                    #                 file_name=os.path.basename(latest_json),
                    #                 mime="application/json"
                    #             )
                    #
                    #         except Exception as e:
                    #             st.error(f"加载JSON数据失败: {e}")

                except Exception as e:
                    st.error(f"构建知识图谱失败: {e}")
                    st.info("请确保已安装所需依赖: pip install transformers torch networkx pyvis")

        # 隐藏已有可视化文件部分
        # # 查看已有图谱
        # if os.path.exists(output_dir):
        #     existing_htmls = [f for f in os.listdir(output_dir) if f.endswith('.html')]
        #     if existing_htmls:
        #         st.divider()
        #         st.subheader("已有可视化文件")
        #
        #         selected_html = st.selectbox(
        #             "选择可视化文件",
        #             options=existing_htmls,
        #             help="选择要查看的知识图谱可视化文件"
        #         )
        #
        #         if selected_html:
        #             html_path = os.path.join(output_dir, selected_html)
        #             try:
        #                 with open(html_path, 'r', encoding='utf-8') as f:
        #                     html_content = f.read()
        #
        #                 st.components.v1.html(html_content, height=500, scrolling=True)
        #
        #                 # 控制按钮
        #                 col1, col2 = st.columns(2)
        #                 with col1:
        #                     st.download_button(
        #                         label="下载HTML",
        #                         data=html_content,
        #                         file_name=selected_html,
        #                         mime="text/html"
        #                     )
        #                 with col2:
        #                     if st.button("删除文件"):
        #                         os.remove(html_path)
        #                         st.success("文件已删除")
        #                         st.rerun()
        #
        #             except Exception as e:
        #                 st.error(f"加载文件失败: {e}")

    st.divider()
    st.subheader("History")
    sessions = memory.list_sessions(user_id=st.session_state.user_id)
    if sessions:
        options = [
            f"{s['session_id']} | {s.get('last_updated','')}"
            for s in sessions
        ]
        selected = st.selectbox("Select Session", options)
        selected_id = selected.split(" | ")[0] if selected else None
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View Session") and selected_id:
                data = memory.load_session(selected_id)
                if data and data.get("messages"):
                    # update the working conversation so the chat area reflects
                    # the loaded history and further questions will continue
                    st.session_state.messages = data["messages"]
                    st.session_state.session_id = selected_id

                    with st.expander(f"Session {selected_id}", expanded=True):
                        for msg in data["messages"]:
                            # try to be a bit smarter about role detection in case
                            # we later store System/Tool messages
                            if isinstance(msg, HumanMessage):
                                role = "user"
                            elif isinstance(msg, AIMessage):
                                role = "assistant"
                            else:
                                # fallback to a generic label
                                role = getattr(msg, "type_name", "system")
                            st.markdown(f"**{role}**: {msg.content}")
        with col2:
            if st.button("Delete Session") and selected_id:
                memory.delete_session(selected_id)
                st.rerun()
    else:
        st.caption("No history for this user.")
    if st.button("Clear History"):
        st.session_state.messages = []
        st.session_state.agent_state_context = {
            "current_topic": "General Knowledge",
            "conversation_summary": None,
            "summarized_msg_count": 0
        }
        st.rerun()

# --- Chat Interface ---

# Display chat history
for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(msg.content)

# Handle user input
if user_input := st.chat_input("Ask your question..."):
    # 1. Display User Message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # 2. Add to history
    user_msg_obj = HumanMessage(content=user_input)
    
    # NOTE: We must ensure st.session_state.messages is up to date before creating state
    current_messages = st.session_state.messages + [user_msg_obj]
    st.session_state.messages = current_messages # Optimistic update

    # --- knowledge graph lookup --- (暂时禁用)
    # try:
    #     from chattutor.core.tools import kg_search
    #     if kg_search is not None and hasattr(kg_search, "invoke"):
    #         kg_result = kg_search.invoke({"query": user_input})
    #         if kg_result:
    #             if kg_result.startswith("Error:"):
    #                 # display as warning so user knows why KG search failed
    #                 with st.chat_message("assistant"):
    #                     st.warning(kg_result + " (install chromadb/langchain?)")
    #             else:
    #                 with st.chat_message("assistant"):
    #                     st.markdown(f"🔍 **Knowledge Graph Results:**\n{kg_result}")
    # except Exception:
    #     # ignore if tool not available or invocation fails
    #     pass

    # 3. Construct Agent State
    current_state = {
        "messages": current_messages, 
        "session_id": st.session_state.session_id,
        "user_id": st.session_state.user_id,
        "current_topic": st.session_state.agent_state_context["current_topic"],
        "conversation_summary": st.session_state.agent_state_context.get("conversation_summary"),
        "summarized_msg_count": st.session_state.agent_state_context.get("summarized_msg_count", 0),
        # Initialize other fields
        "plan": None,
        "tutor_output": None,
        "judge_output": None,
        "inquiry_output": None,
        "summary_output": None,
        "should_exit": False,
        "last_intent": None
    }

    # 4. Invoke Agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # The graph returns the updated state
                result_state = graph.invoke(current_state)
                
                # Extract the latest AI message
                all_messages = result_state["messages"]
                
                # We need to find the NEW messages generated by the AI
                # Since we passed `current_messages` as input, any message AFTER that length is new
                # But LangGraph might return a completely new list or just append. 
                # Usually it keeps the history.
                
                if all_messages:
                    last_msg = all_messages[-1]
                    if isinstance(last_msg, AIMessage):
                        st.markdown(last_msg.content)
                    
                    # Update session state with the FULL list from the Agent
                    # This ensures we capture any intermediate tool messages or corrections
                    st.session_state.messages = all_messages
                    
                    # Update context 
                    st.session_state.agent_state_context["current_topic"] = result_state.get("current_topic")
                    st.session_state.agent_state_context["conversation_summary"] = result_state.get("conversation_summary")
                    st.session_state.agent_state_context["summarized_msg_count"] = result_state.get("summarized_msg_count", 0)
                    
            except Exception as e:
                st.error(f"Error during processing: {e}")
