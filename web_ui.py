# ChatTutor-main/web_ui.py
import streamlit as st
import requests
import os

# ================= 配置与初始化 =================
API_BASE_URL = "http://127.0.0.1:8000/api/v1"
SESSION_ID = "web_session_1"
TOPIC = "General"

# 1. 改为居中布局 (centered)，阅读体验更好
st.set_page_config(page_title="ChatTutor 智能导师", page_icon="🎓", layout="centered")

# 2. 注入强大的自定义 CSS 魔法
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认的顶部菜单和底部水印 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 优化全局字体 */
    body {
        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    }
    
    /* 主标题渐变色特效 */
    .main-title {
        background: -webkit-linear-gradient(45deg, #4A90E2, #50E3C2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5em;
        font-weight: 900;
        text-align: center;
        margin-bottom: 0.1em;
        margin-top: 1em;
    }
    
    .sub-title {
        text-align: center;
        color: #888;
        font-size: 1.1em;
        margin-bottom: 3em;
    }

    /* 优化侧边栏背景 */
    [data-testid="stSidebar"] {
        background-color: #F8F9FA;
        border-right: 1px solid #E9ECEF;
    }
    
    /* 聊天气泡间距微调 */
    .stChatMessage {
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

# ================= 侧边栏：学习档案区 =================
with st.sidebar:
    st.markdown("## 📚 我的学习档案")
    st.caption("AI Tutor 自动为您沉淀的深度知识简报。")
    st.divider()
    
    notes_dir = os.path.join(os.path.dirname(__file__), "memory", "notes")
    
    if os.path.exists(notes_dir):
        note_files = [f for f in os.listdir(notes_dir) if f.endswith(".md")]
        if not note_files:
            st.info("💡 暂无笔记。多和 Tutor 聊聊，结束会话时会自动生成哦！")
        else:
            for file_name in sorted(note_files, reverse=True):
                # 去掉后缀名，让标题更干净
                clean_title = file_name.replace('.md', '')
                with st.expander(f"📄 {clean_title}", expanded=False):
                    file_path = os.path.join(notes_dir, file_name)
                    with open(file_path, "r", encoding="utf-8") as f:
                        st.markdown(f.read())
    else:
        st.warning("笔记文件夹未就绪。")

# ================= 主界面：欢迎与聊天区 =================
if not st.session_state.messages:
    # --- 空白页面的欢迎 UI ---
    st.markdown('<div class="main-title">ChatTutor</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">你的专属 AI 导师，随时随地开启深度学习 🚀</div>', unsafe_allow_html=True)
    
    # 精美的引导卡片
    cols = st.columns(3)
    with cols[0]:
        st.info("🧮 **理科答疑**\n\n傅里叶变换的核心公式和物理意义是什么？")
    with cols[1]:
        st.info("💻 **代码解析**\n\nPython 报错 [WinError 10061] 应该怎么解决？")
    with cols[2]:
        st.info("📚 **概念提炼**\n\n请用通俗的语言，为我解释什么是量子纠缠。")
else:
    # --- 有聊天记录时的小标题 ---
    st.markdown("### 🎓 ChatTutor 会话中...")
    st.divider()

# 1. 渲染历史聊天记录 (引入了专属 Emoji 头像)
for msg in st.session_state.messages:
    avatar_icon = "🧑‍🎓" if msg["role"] == "user" else "🦉"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        st.markdown(msg["content"])

# 2. 接收用户输入
if prompt := st.chat_input("输入你的疑问，支持 LaTeX 数学公式和代码块..."):
    # 显示用户消息
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 显示 AI 回复与加载动画
    with st.chat_message("assistant", avatar="🦉"):
        with st.spinner("Tutor 正在翻阅知识库与深度思考... 🧠"):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/chat",
                    json={"session_id": SESSION_ID, "message": prompt, "topic": TOPIC},
                    timeout=120
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get("reply", "抱歉，生成回复失败。")
                    
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    
                    # 结束对话时，右下角弹出优雅的 Toast 通知
                    if data.get("is_concluded"):
                        st.toast('🎉 本次学习已结束！Tutor 已将总结报告放入了左侧边栏。', icon='✅')
                else:
                    st.error(f"接口调用失败: {response.status_code}")
            
            except requests.exceptions.ConnectionError:
                st.error("❌ 无法连接到后端服务器！请确保您已经启动了 FastAPI (uvicorn app.main:app...)")
            except Exception as e:
                st.error(f"❌ 发生未知网络错误: {str(e)}")
#streamlit run web_ui.py运行程序