# ChatTutor-main/web_ui.py - React 样式版本
import streamlit as st
import requests
import os

# ================= 配置与初始化 =================
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")

# 1. 改为居中布局 (centered)，阅读体验更好
st.set_page_config(
    page_title="阿城 你的学习同桌",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

# 2. 使用 React 构建的 CSS
css_path = os.path.join(os.path.dirname(__file__), "web_static", "assets")
if os.path.exists(css_path):
    css_files = [f for f in os.listdir(css_path) if f.endswith(".css")]
    for css_file in css_files:
        full_path = os.path.join(css_path, css_file)
        with open(full_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 3. 注入自定义 CSS 覆盖 Streamlit 默认样式
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

    /* 主标题样式 */
    .main-title {
        font-size: 3em;
        font-weight: 900;
        text-align: center;
        margin-bottom: 0.2em;
        margin-top: 1em;
        background: linear-gradient(135deg, #3B82F6 0%, #14B8A6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .sub-title {
        text-align: center;
        color: #6B7280;
        font-size: 1.1em;
        margin-bottom: 2em;
    }

    /* 聊天界面优化 */
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }

    /* 登录表单样式 */
    .stTextInput > div > div > input {
        border-radius: 10px;
    }

    /* 按钮样式 */
    .stButton > button {
        border-radius: 10px;
        padding: 12px 24px;
        font-weight: 600;
        background: linear-gradient(135deg, #3B82F6 0%, #14B8A6 100%);
        border: none;
        color: white;
        transition: all 0.2s;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }

    /* 卡片容器样式 */
    .demo-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #E5E7EB;
        transition: all 0.2s;
    }

    .demo-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
</style>
""", unsafe_allow_html=True)


# ================= 状态管理 =================
# 初始化登录状态 - 首次访问时重置为未登录
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.token = ""
    st.session_state.token_expires_at = 0
    st.session_state.messages = []
    st.session_state.session_id = ""
    st.session_state.task_id = "task_default"
else:
    # 如果已存在会话，确保所有状态都存在
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "token" not in st.session_state:
        st.session_state.token = ""
    if "token_expires_at" not in st.session_state:
        st.session_state.token_expires_at = 0
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = ""
    if "task_id" not in st.session_state:
        st.session_state.task_id = "task_default"

# 检查 Token 是否过期（24 小时）
import time

def is_token_valid() -> bool:
    """检查 Token 是否有效且未过期。"""
    if not st.session_state.token:
        return False
    if not st.session_state.token_expires_at:
        return False
    # 检查是否过期
    if time.time() > st.session_state.token_expires_at:
        logout()
        return False
    return True

# 每次加载都检查登录状态
if st.session_state.logged_in and not is_token_valid():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.token = ""


# ================= 认证函数 =================
def login(username: str, password: str) -> tuple[bool, str]:
    """
    Login with username and password.
    Returns (success, message).
    """
    import time

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            data={"username": username, "password": password},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.username = username
            st.session_state.logged_in = True
            # 设置 Token 过期时间（24 小时 = 86400 秒）
            st.session_state.token_expires_at = time.time() + data.get("expires_in", 86400)
            return True, "登录成功!"
        elif response.status_code == 401:
            return False, "用户名或密码错误"
        else:
            return False, f"登录失败：{response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "无法连接到服务器，请检查后端是否启动"
    except Exception as e:
        return False, f"登录失败：{str(e)}"


def register(username: str, password: str) -> tuple[bool, str]:
    """
    Register a new user.
    Returns (success, message).
    """
    import time

    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            json={"username": username, "password": password},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.username = username
            st.session_state.logged_in = True
            # 设置 Token 过期时间（24 小时 = 86400 秒）
            st.session_state.token_expires_at = time.time() + data.get("expires_in", 86400)
            return True, "注册成功!"
        elif response.status_code == 400:
            error = response.json().get("detail", "注册失败")
            return False, error
        else:
            return False, f"注册失败：{response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "无法连接到服务器，请检查后端是否启动"
    except Exception as e:
        return False, f"注册失败：{str(e)}"


def logout():
    """Logout current user."""
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.token = ""
    st.session_state.token_expires_at = 0
    st.session_state.messages = []
    st.session_state.session_id = ""


def get_headers() -> dict:
    """Get request headers with authorization."""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


# ================= 登录/注册页面 =================
def show_login_page():
    """Show login and register page."""
    # 页面标题
    st.markdown('<div class="main-title">阿城 你的学习同桌</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">随时随地开启深度学习 🚀</div>',
        unsafe_allow_html=True,
    )

    # 选项卡：登录/注册
    tab1, tab2 = st.tabs(["🔐 登录", "📝 注册"])

    with tab1:
        st.markdown("### 欢迎回来")

        login_username = st.text_input(
            "用户名",
            key="login_username",
            placeholder="请输入用户名（至少 3 个字符）",
        )
        login_password = st.text_input(
            "密码",
            key="login_password",
            type="password",
            placeholder="请输入密码（至少 6 个字符）",
        )

        if st.button("登录", key="login_btn", use_container_width=True):
            if not login_username or not login_password:
                st.error("请输入用户名和密码")
            elif len(login_username) < 3:
                st.error("用户名至少 3 个字符")
            elif len(login_password) < 6:
                st.error("密码至少 6 个字符")
            else:
                success, message = login(login_username, login_password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    with tab2:
        st.markdown("### 创建新账户")

        reg_username = st.text_input(
            "用户名",
            key="reg_username",
            placeholder="请输入用户名（至少 3 个字符）",
        )
        reg_password = st.text_input(
            "密码",
            key="reg_password",
            type="password",
            placeholder="请输入密码（至少 6 个字符）",
        )
        reg_confirm = st.text_input(
            "确认密码",
            key="reg_confirm",
            type="password",
            placeholder="请再次输入密码",
        )

        if st.button("注册", key="register_btn", use_container_width=True):
            if not reg_username or not reg_password:
                st.error("请输入用户名和密码")
            elif len(reg_username) < 3:
                st.error("用户名至少 3 个字符")
            elif len(reg_password) < 6:
                st.error("密码至少 6 个字符")
            elif reg_password != reg_confirm:
                st.error("两次输入的密码不一致")
            else:
                success, message = register(reg_username, reg_password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    # 引导卡片
    st.divider()
    st.markdown("### 💡 开始学习")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("""
        <div class="demo-card">
            <p style="color: #3B82F6; font-weight: 600; margin-bottom: 8px;">🧮 理科答疑</p>
            <p style="color: #6B7280; font-size: 14px; line-height: 1.6;">傅里叶变换的核心公式和物理意义是什么？</p>
        </div>
        """, unsafe_allow_html=True)
    with cols[1]:
        st.markdown("""
        <div class="demo-card">
            <p style="color: #3B82F6; font-weight: 600; margin-bottom: 8px;">💻 代码解析</p>
            <p style="color: #6B7280; font-size: 14px; line-height: 1.6;">Python 报错 [WinError 10061] 应该怎么解决？</p>
        </div>
        """, unsafe_allow_html=True)
    with cols[2]:
        st.markdown("""
        <div class="demo-card">
            <p style="color: #3B82F6; font-weight: 600; margin-bottom: 8px;">📚 概念提炼</p>
            <p style="color: #6B7280; font-size: 14px; line-height: 1.6;">请用通俗的语言，为我解释什么是量子纠缠。</p>
        </div>
        """, unsafe_allow_html=True)


# ================= 聊天页面 =================
def show_chat_page():
    """Show chat page for logged-in users."""
    # 侧边栏：用户信息和学习档案
    with st.sidebar:
        # 用户信息
        st.markdown(f"### 👤 {st.session_state.username}")
        st.caption("已登录")

        if st.button("退出登录", key="logout_btn", use_container_width=True):
            logout()
            st.rerun()

        st.divider()

        # 学习档案区
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
                    clean_title = file_name.replace('.md', '')
                    with st.expander(f"📄 {clean_title}", expanded=False):
                        file_path = os.path.join(notes_dir, file_name)
                        with open(file_path, "r", encoding="utf-8") as f:
                            st.markdown(f.read())
        else:
            st.warning("笔记文件夹未就绪。")

    # 主界面
    if not st.session_state.messages:
        # 空白页面的欢迎 UI
        st.markdown('<div class="main-title">阿城 你的学习同桌</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="sub-title">随时随地开启深度学习 🚀</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### 🎓 ChatTutor 会话中...")
        st.divider()

    # 渲染历史聊天记录
    for msg in st.session_state.messages:
        avatar_icon = "🧑‍" if msg["role"] == "user" else "🦉"
        with st.chat_message(msg["role"], avatar=avatar_icon):
            st.markdown(msg["content"])

    # 接收用户输入
    if prompt := st.chat_input("输入你的疑问，支持 LaTeX 数学公式和代码块..."):
        # 显示用户消息
        with st.chat_message("user", avatar="🧑‍"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 显示 AI 回复与加载动画
        with st.chat_message("assistant", avatar="🦉"):
            with st.spinner("Tutor 正在翻阅知识库与深度思考... 🧠"):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/chat",
                        json={
                            "session_id": st.session_state.session_id,
                            "message": prompt,
                            "topic": "General",
                            "task_id": st.session_state.task_id,
                        },
                        headers=get_headers(),
                        timeout=120,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        reply = data.get("reply", "抱歉，生成回复失败。")

                        # 更新 session_id
                        st.session_state.session_id = data.get("session_id", st.session_state.session_id)

                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})

                        # 结束对话时，弹出 Toast 通知
                        if data.get("is_concluded"):
                            st.toast(
                                '🎉 本次学习已结束！Tutor 已将总结报告放入了左侧边栏。',
                                icon='✅',
                            )
                    elif response.status_code == 401:
                        st.error("登录已过期，请重新登录")
                        logout()
                        st.rerun()
                    elif response.status_code == 429:
                        st.error("请求太频繁，请稍后再试")
                    else:
                        st.error(f"接口调用失败：{response.status_code}")

                except requests.exceptions.ConnectionError:
                    st.error("❌ 无法连接到后端服务器！请确保您已经启动了 FastAPI (uvicorn app.main:app...)")
                except Exception as e:
                    st.error(f"❌ 发生未知网络错误：{str(e)}")


# ================= 主入口 =================
def main():
    """Main entry point."""
    # 每次运行都检查登录状态和 Token 有效性
    if not st.session_state.logged_in or not is_token_valid():
        # 确保未登录时清除所有状态
        if not st.session_state.logged_in:
            st.session_state.messages = []
            st.session_state.session_id = ""
        show_login_page()
    else:
        show_chat_page()


# Streamlit 直接执行此代码
main()
