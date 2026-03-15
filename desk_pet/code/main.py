# desk_pet/code/main.py
import sys
import os
import signal 
import json
import random
import time
import threading
from datetime import datetime
import requests

# ======= 【核心修复：禁用 Chromium 硬件加速，防止透明窗口渲染崩溃】 =======
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing --log-level=3"

# 【补充：屏蔽因靠近屏幕边缘动态变大而产生的无害 Qt 窗口警告】
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"
# ======================================================================================

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QLabel, QMenu, QPushButton)
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent, QUrl, QTimer, QUrlQuery
from PyQt6.QtGui import QMovie, QFont, QAction, QPixmap, QPainter, QDesktopServices
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineUrlScheme

PET_SCHEME = b"pet"
DEFAULT_TASK_TITLE = "新的学习"
DEFAULT_TASK_ICON = "✨"

try:
    scheme = QWebEngineUrlScheme(PET_SCHEME)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)
except Exception:
    pass

from config import HTML_TEMPLATE, BASE_DIR
from text_worker import AgentWorker
from voice_worker import AudioRecorder, VoiceAgentWorker
from pet_controller import PetController


class PetLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_flipped = False

    def set_flipped(self, flipped):
        if self.is_flipped != flipped:
            self.is_flipped = flipped
            self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = None
        
        if self.movie() and self.movie().currentPixmap() and not self.movie().currentPixmap().isNull():
            pixmap = self.movie().currentPixmap()
        elif self.pixmap() and not self.pixmap().isNull():
            pixmap = self.pixmap()
            
        if pixmap:
            x = int((self.width() - pixmap.width()) / 2)
            y = int((self.height() - pixmap.height()) / 2)
            
            if self.is_flipped:
                painter.translate(self.width(), 0)
                painter.scale(-1, 1)
                
            painter.drawPixmap(x, y, pixmap)


class PetWebPage(QWebEnginePage):
    def __init__(self, parent, link_handler):
        super().__init__(parent)
        self._link_handler = link_handler

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "pet":
            if self._link_handler:
                self._link_handler(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class ChatTutorPet(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self._drag_start_pos = QPoint() 
        self._is_dragging = False       
        
        self.gif_size = QSize(150, 150)
        self.assets = {}
        
        self.init_ui()
        self.init_assets()      
        self.init_agent()
        self._create_draft_task()
        self.init_controller()  
        self.active_stream_message_id = None
        self.last_plan_proposal = None
        self.last_plan_status = None
        self.plan_proposals = {}
        self.pending_plan_apply = False
        self.last_plan_message_id = None

        # ================= 新增：阿城的待机互动引擎 =================
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.show_idle_bubble)
        # 默认 20000 毫秒（20秒）触发一次
        self.idle_timer.start(20000) 
        
        self.bubble_hide_timer = QTimer(self)
        self.bubble_hide_timer.timeout.connect(self.hide_idle_bubble)
        # ============================================================

    def init_ui(self):
        font = QFont("Microsoft YaHei", 10)
        QApplication.setFont(font)
        # Windows/Linux 下的标准置顶与无边框配置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(12) 
        
        self.chat_container = QWidget()
        self.chat_container.setMinimumHeight(40) 
        
        # 将宽度调宽，强制固定宽度为 300px
        self.chat_container.setFixedWidth(300) 
        
        self.chat_container.setStyleSheet("background-color: rgba(245, 245, 247, 230); border: 1px solid rgba(200, 200, 220, 150); border-radius: 12px;")
        
        container_layout = QVBoxLayout(self.chat_container)
        container_layout.setContentsMargins(4, 4, 4, 4)
        
        self.web_view = QWebEngineView()
        self.web_view.setPage(PetWebPage(self.web_view, self._handle_pet_link))
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.web_view.setHtml(HTML_TEMPLATE)
        # 接收前端通过 title 传回来的高度信息
        self.web_view.titleChanged.connect(self.adjust_web_height)
        
        container_layout.addWidget(self.web_view)
        self.chat_container.hide()

        self.pet_label = PetLabel(self)
        self.pet_label.setFixedSize(self.gif_size)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("想问点什么？按回车发送...")
        
        # 输入框宽度调整为 250px，与气泡容器适配
        self.input_field.setMinimumWidth(250)
        
        self.input_field.setStyleSheet("background-color: rgba(255, 255, 255, 240); border: 2px solid #E0E0E0; border-radius: 15px; padding: 6px 14px;")
        self.input_field.returnPressed.connect(self.send_message)
        
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setFixedSize(36, 36)
        self.voice_btn.setStyleSheet("""
            QPushButton { background-color: #ffffff; border: 2px solid #E0E0E0; border-radius: 18px; font-size: 16px; } 
            QPushButton:pressed { background-color: #e0e0e0; }
        """)
        self.voice_btn.pressed.connect(self.start_voice_recording)
        self.voice_btn.released.connect(self.stop_voice_recording)
        
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.voice_btn)
        
        self.input_container = QWidget()
        self.input_container.setLayout(input_layout)
        self.input_container.hide()

        # ================= 鏂板锛氱嫭绔嬭鍒掓搷浣滄寜閽尯 =================
        self.plan_action_container = QWidget()
        plan_layout = QHBoxLayout(self.plan_action_container)
        plan_layout.setContentsMargins(0, 0, 0, 0)
        plan_layout.setSpacing(6)

        self.plan_confirm_btn = QPushButton("确认计划")
        self.plan_resume_btn = QPushButton("继续计划")
        self.plan_exit_btn = QPushButton("退出计划")

        plan_btn_style = """
            QPushButton { background-color: #ecfdf3; border: 1px solid rgba(34, 197, 94, 0.5); border-radius: 10px; padding: 4px 8px; font-size: 11px; color: #166534; }
            QPushButton:pressed { background-color: #dcfce7; }
            QPushButton:disabled { color: rgba(22, 101, 52, 0.5); }
        """
        for btn in (self.plan_confirm_btn, self.plan_resume_btn, self.plan_exit_btn):
            btn.setStyleSheet(plan_btn_style)
            btn.setFixedHeight(24)

        self.plan_confirm_btn.clicked.connect(self._on_plan_confirm_clicked)
        self.plan_resume_btn.clicked.connect(self._on_plan_resume_clicked)
        self.plan_exit_btn.clicked.connect(self._on_plan_exit_clicked)

        plan_layout.addWidget(self.plan_confirm_btn)
        plan_layout.addWidget(self.plan_resume_btn)
        plan_layout.addWidget(self.plan_exit_btn)
        self.plan_action_container.hide()
        # ============================================================
        
        # ================= 新增：轻量级互动气泡 UI =================
        self.speech_bubble = QLabel()
        self.speech_bubble.setWordWrap(True)
        self.speech_bubble.setFixedWidth(220)
        self.speech_bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speech_bubble.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.95);
            border: 2px solid #86efac;
            border-radius: 15px;
            padding: 10px;
            color: #166534;
            font-weight: bold;
            font-size: 12px;
        """)
        self.speech_bubble.hide()
        # ============================================================

        self.layout.addWidget(self.chat_container) 
        self.layout.addWidget(self.plan_action_container, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(self.input_container) 
        self.layout.addWidget(self.speech_bubble, alignment=Qt.AlignmentFlag.AlignHCenter) # 气泡在本体上方
        self.layout.addWidget(self.pet_label, alignment=Qt.AlignmentFlag.AlignHCenter) 

    # ============ 新增：闲置气泡控制逻辑 ============
    def reset_idle_timer(self):
        """用户有任何交互时，重置待机时间"""
        self.idle_timer.start(20000) # 重新开始20秒倒计时
        self.hide_idle_bubble()

    def show_idle_bubble(self):
        """触发闲置互动"""
        # 如果当前正处于聊天模式，就不打扰用户
        if not self.chat_container.isHidden():
            return
            
        current_state = self.controller.state
        
        # 【修改】：把 WALK, WALK1, WALK2 全都加进来，无论哪种走路状态都不会弹气泡
        ignore_states = [
            "DRAGGED", "FALLING", "FELL", "JUMP", "GETUP", "THINKING",
            "SLEEP", "STAND_READING", "SIT_READING", "WALK", "WALK1", "WALK2" 
        ]
        
        if current_state in ignore_states:
            return
            
        phrases = [
            "已经学了5分钟啦，快来和阿城一起玩耍吧，放松一下身心吧！🍃",
            "阿城陪你很久啦，要不要喝口水休息一下呢？☕",
            "遇到难题了吗？戳戳阿城，我来帮你解答！✨",
            "眼睛累了吧？阿城提醒你看看远方的风景哦！👀",
            "今天也要元气满满哦！阿城为你加油！💪",
            "你在看什么呀？阿城也想一起看！👀"
        ]
        
        # ====== 新增：冻结UI渲染，防止布局抖动闪烁 ======
        self.setUpdatesEnabled(False)
        
        self.speech_bubble.setText(random.choice(phrases))
        self.speech_bubble.show()
        self.adjustSize()
        self.update_position(self.controller.pet_x, self.controller.pet_y)
        self._update_plan_action_buttons()
        
        # 恢复UI渲染
        self.setUpdatesEnabled(True)
        # ===============================================
        
        # 气泡展示 5 秒后自动消失
        self.bubble_hide_timer.start(5000)

    def hide_idle_bubble(self):
        """隐藏气泡"""
        if not self.speech_bubble.isHidden():
            # ====== 新增：冻结UI渲染，防止隐藏时闪烁 ======
            self.setUpdatesEnabled(False)
            
            self.speech_bubble.hide()
            self.bubble_hide_timer.stop()
            self.adjustSize()
            self.update_position(self.controller.pet_x, self.controller.pet_y)
            
            # 恢复UI渲染
            self.setUpdatesEnabled(True)
            # ===============================================
    # ===============================================

    # ============ 自适应高度调节 ============
    def adjust_web_height(self, title):
        if title.startswith("HEIGHT:"):
            try:
                # 解析出前端网页的实际内容高度
                h = int(float(title.split(":")[1]))
                # 预留上下 padding 的空间，并设置最小/最大高度防止越界
                new_height = max(40, h + 15) 
                
                # ====== 核心修改：高度上限修改为 450 ======
                new_height = min(new_height, 450) 
                # ==========================================
                
                # 只有高度真的变化了才重置，避免抖动
                if self.chat_container.height() != new_height:
                    self.chat_container.setFixedHeight(new_height)
                    self.adjustSize() # 强制更新整个桌宠窗口尺寸
                    self.update_position(self.controller.pet_x, self.controller.pet_y)
            except Exception:
                pass
    # ========================================

    def init_agent(self):
        self.api_base_url = "http://127.0.0.1:8000/api/v1"
        self.task_id = None
        self.task_title = None
        self.session_id = None
        self.topic = "General"
        self.is_draft_task = False
        self.draft_task_id = None
        self.draft_task_title = None
        self.draft_task_icon = None
        self.draft_has_message = False

    def _run_js(self, js_code: str):
        QTimer.singleShot(0, lambda: self.web_view.page().runJavaScript(js_code))

    def _handle_pet_link(self, url: QUrl):
        host = url.host()
        path = url.path().lstrip("/")
        action = f"{host}/{path}" if host else path
        if action.endswith("/"):
            action = action[:-1]
        query = QUrlQuery(url)
        message_id = query.queryItemValue("mid") or None
        if action == "plan/confirm":
            self._confirm_plan_update_async(message_id)
        elif action == "plan/resume":
            self._plan_session_action_async("resume")
        elif action == "plan/exit":
            self._plan_session_action_async("exit")

    def _refresh_tasks(self):
        try:
            response = requests.get(f"{self.api_base_url}/tasks", timeout=5)
            response.raise_for_status()
            tasks = response.json().get("tasks", [])
        except Exception:
            tasks = []
        if self.is_draft_task and not self.draft_has_message and self.draft_task_id:
            exists = any(t.get("id") == self.draft_task_id for t in tasks)
            if not exists:
                tasks = [
                    {
                        "id": self.draft_task_id,
                        "title": self.draft_task_title or DEFAULT_TASK_TITLE,
                        "icon": self.draft_task_icon or DEFAULT_TASK_ICON,
                        "status": "draft",
                    }
                ] + tasks
        return tasks


    def _generate_task_id(self):
        stamp = int(time.time() * 1000)
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
        if stamp == 0:
            return "task_0"
        chars = []
        while stamp:
            stamp, rem = divmod(stamp, 36)
            chars.append(alphabet[rem])
        return "task_" + "".join(reversed(chars))

    def _create_draft_task(self, title=None, icon=None):
        self._discard_unused_draft()
        task_id = self._generate_task_id()
        self.task_id = task_id
        self.task_title = title or DEFAULT_TASK_TITLE
        self.topic = self.task_title or "General"
        self.session_id = None
        self.is_draft_task = True
        self.draft_task_id = task_id
        self.draft_task_title = self.task_title
        self.draft_task_icon = icon or DEFAULT_TASK_ICON
        self.draft_has_message = False
        self.last_plan_proposal = None
        self.last_plan_status = None
        self.last_plan_message_id = None
        self._update_plan_action_buttons()

    def _discard_unused_draft(self, next_task_id=None):
        if not self.is_draft_task or self.draft_has_message:
            return
        if next_task_id and next_task_id == self.draft_task_id:
            return
        self.is_draft_task = False
        self.draft_task_id = None
        self.draft_task_title = None
        self.draft_task_icon = None
        self.draft_has_message = False

    def _upsert_task_async(self, task_id, title, icon):
        current_task_id = task_id

        def _do_request():
            ok = False
            try:
                response = requests.post(
                    f"{self.api_base_url}/tasks",
                    json={
                        "task_id": task_id,
                        "title": title,
                        "icon": icon,
                        "status": "active",
                    },
                    timeout=5,
                )
                ok = response.ok
            except Exception:
                ok = False
            if not ok and self.task_id == current_task_id:
                self.is_draft_task = True

        threading.Thread(target=_do_request, daemon=True).start()

    def _ensure_task_for_send(self):
        if not self.task_id:
            self._create_draft_task()
        if not self.is_draft_task and not self.session_id:
            self._load_latest_session_sync(self.task_id)
        if self.is_draft_task:
            self.draft_has_message = True
            title = self.task_title or DEFAULT_TASK_TITLE
            icon = self.draft_task_icon or DEFAULT_TASK_ICON
            self._upsert_task_async(self.task_id, title, icon)
            self.is_draft_task = False

    def _update_session_id(self, session_id: str):
        if session_id:
            self.session_id = session_id

    def _load_latest_session_async(self, task_id: str):
        if not task_id:
            return

        def _do_request():
            try:
                response = requests.get(
                    f"{self.api_base_url}/history/tasks/{task_id}/sessions",
                    timeout=5,
                )
                if response.ok:
                    data = response.json()
                    sessions = data.get("sessions", [])
                    if not sessions:
                        if self.task_id == task_id:
                            self._run_js("if (typeof clearChat === 'function') { clearChat(); }")
                        return
                    session_id = sessions[0].get("session_id")
                    if session_id and self.task_id == task_id:
                        self.session_id = session_id
                        self._load_session_messages_async(session_id)
            except Exception:
                pass

        threading.Thread(target=_do_request, daemon=True).start()

    def _render_history_messages(self, messages):
        parts = ["if (typeof clearChat === 'function') { clearChat(); }"]
        last_role = None
        for msg in messages or []:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                parts.append(f"_createMessageRow({json.dumps(content)}, true, null);")
                last_role = "user"
            elif role == "assistant":
                if last_role == "user":
                    parts.append(f"_createMessageRow({json.dumps(content)}, false, null);")
                else:
                    parts.append("startAssistantMessage(null);")
                    parts.append(f"appendAssistantDelta(null, {json.dumps(content)});")
                    parts.append("finishAssistantMessage(null);")
                last_role = "assistant"
        self._run_js("".join(parts))

    def _load_session_messages_async(self, session_id: str):
        if not session_id:
            return

        def _do_request():
            try:
                response = requests.get(
                    f"{self.api_base_url}/history/sessions/{session_id}/messages",
                    timeout=5,
                )
                if response.ok:
                    data = response.json()
                    messages = data.get("messages", [])
                    if self.session_id != session_id:
                        return
                    self._render_history_messages(messages)
            except Exception:
                pass

        threading.Thread(target=_do_request, daemon=True).start()

    def _load_latest_session_sync(self, task_id: str):
        if not task_id:
            return
        try:
            response = requests.get(
                f"{self.api_base_url}/history/tasks/{task_id}/sessions",
                timeout=3,
            )
            if response.ok:
                data = response.json()
                sessions = data.get("sessions", [])
                if not sessions:
                    return
                session_id = sessions[0].get("session_id")
                if session_id and self.task_id == task_id:
                    self.session_id = session_id
        except Exception:
            pass


    def _set_active_task(self, task_id, title):
        if task_id and not str(task_id).startswith("task_"):
            task_id = f"task_{task_id}"
        self._discard_unused_draft(next_task_id=task_id)
        self.task_id = task_id
        self.task_title = title
        self.topic = title or "General"
        self.session_id = None
        self.is_draft_task = False
        self.draft_task_id = None
        self.draft_task_title = None
        self.draft_task_icon = None
        self.last_plan_proposal = None
        self.last_plan_status = None
        self.last_plan_message_id = None
        self._update_plan_action_buttons()
        self._run_js("if (typeof clearChat === 'function') { clearChat(); }")
        self._load_latest_session_async(task_id)
        self._load_plan_state_async()

    def _load_plan_state_async(self):
        if not self.task_id:
            return

        def _do_request():
            try:
                response = requests.get(
                    f"{self.api_base_url}/notes/task",
                    params={"task_id": self.task_id},
                    timeout=5,
                )
                if response.ok:
                    data = response.json()
                    draft_plan = data.get("draft_plan")
                    plan_session = data.get("_plan_session", {}) if isinstance(data, dict) else {}
                    status = None
                    if isinstance(plan_session, dict):
                        status = plan_session.get("status")
                    self.last_plan_proposal = draft_plan if isinstance(draft_plan, dict) else None
                    self.last_plan_status = status
                    self.last_plan_message_id = None
                    if self.last_plan_proposal:
                        self._run_js("startAssistantMessage(null);")
                        self._run_js(
                            f"updatePlanCard({json.dumps(draft_plan)}, {json.dumps(status)}, null);"
                        )
                    self._run_js(f"updatePlanStatusBanner({json.dumps(status)});")
                    self._update_plan_action_buttons()
            except Exception:
                pass

        threading.Thread(target=_do_request, daemon=True).start()

    def _auto_select_default_task(self):
        tasks = self._refresh_tasks()
        if not tasks:
            return
        active_tasks = [t for t in tasks if t.get("status") == "active"]
        picked = active_tasks[0] if active_tasks else tasks[0]
        task_id = picked.get("id")
        if not task_id:
            return
        title = picked.get("title") or task_id
        self._set_active_task(task_id, title)

    def init_assets(self):
        assets_dir = os.path.normpath(os.path.join(BASE_DIR, "img"))
        
        def load_movie(name):
            path = os.path.join(assets_dir, name)
            if os.path.exists(path):
                m = QMovie(path)
                m.setScaledSize(self.gif_size)
                return m
            return None

        self.assets = {
            "stand": load_movie("stand.gif"),
            "walk1": load_movie("walk1.gif"),
            "walk2": load_movie("walk2.gif"),
            "sit": load_movie("sit.gif"),
            "catching": load_movie("catching.gif"), 
            "felling": load_movie("felling.gif"),
            "fell": load_movie("fell.gif"),
            "say_hi1": load_movie("say_hi1.gif"),
            "say_hi2": load_movie("say_hi2.gif"),
            "thinking": load_movie("thinking.gif"),
            "getup": load_movie("getup.gif"),
            "jump": load_movie("jump.gif"), 
            "sitting": load_movie("sitting.gif"),   
            "standing": load_movie("standing.gif"),
            "sleep": load_movie("sleep.gif"),
            "stand_reading": load_movie("stand_reading.gif"),
            "sit_reading": load_movie("sit_reading.gif"),
        }

    def set_appearance(self, asset_key):
        asset = self.assets.get(asset_key)
        if self.pet_label.movie() == asset and asset is not None:
            return
        if isinstance(asset, QMovie):
            if self.pet_label.movie():
                self.pet_label.movie().stop()
            self.pet_label.setMovie(asset)
            asset.stop() 
            asset.jumpToFrame(0) 
            asset.start()

    def init_controller(self):
        screen_rect = QApplication.primaryScreen().availableGeometry()
        self.controller = PetController(
            screen_rect=screen_rect,
            pet_width=self.gif_size.width(),
            pet_height=self.gif_size.height(),
            win_id=int(self.winId())
        )
        self.controller.position_changed.connect(self.update_position)
        self.controller.appearance_changed.connect(self.set_appearance)
        
        self.controller.direction_changed.connect(self.pet_label.set_flipped)
        
        self.controller.drag_to(self.x() + self.pet_label.x(), self.y() + self.pet_label.y())
        self.controller.change_state("STAND")

    def update_position(self, pet_x, pet_y):
        win_x = pet_x - self.pet_label.x()
        win_y = pet_y - self.pet_label.y()
        self.move(int(win_x), int(win_y))

    def add_bubble(self, text, is_user=False):
        # ====== 核心修复：对齐 JS 函数名并补全参数 ======
        js_code = f"_createMessageRow({json.dumps(text)}, {'true' if is_user else 'false'}, null);"
        self.web_view.page().runJavaScript(js_code)
        # ================================================

    def start_stream_bubble(self, message_id):
        self.active_stream_message_id = message_id
        js_code = f"startAssistantMessage({json.dumps(message_id)});"
        self.web_view.page().runJavaScript(js_code)

    def append_stream_bubble(self, message_id, chunk):
        js_code = f"appendAssistantDelta({json.dumps(message_id)}, {json.dumps(chunk)});"
        self.web_view.page().runJavaScript(js_code)

    def finish_stream_bubble(self, message_id):
        js_code = f"finishAssistantMessage({json.dumps(message_id)});"
        self.web_view.page().runJavaScript(js_code)
        self.active_stream_message_id = None

    # ====== 新增：大模型意图和节点状态的更新方法 ======
    def update_node_status(self, message_id, node_name):
        """更新当前处理节点显示"""
        js_code = f"updateNodeStatus({json.dumps(message_id)}, {json.dumps(node_name)});"
        self.web_view.page().runJavaScript(js_code)

    def update_intent_status(self, intent_text):
        """更新意图识别结果显示"""
        js_code = f"updateIntentStatus({json.dumps(intent_text)});"
        self.web_view.page().runJavaScript(js_code)
    # ==================================================

    def update_plan_proposal(self, plan_proposal, plan_status):
        self.last_plan_proposal = plan_proposal if isinstance(plan_proposal, dict) else None
        self.last_plan_status = plan_status
        message_id = self.active_stream_message_id
        if not message_id and isinstance(plan_proposal, dict):
            message_id = f"plan-{int(time.time() * 1000)}"
        self.last_plan_message_id = message_id
        if message_id and isinstance(plan_proposal, dict):
            self.plan_proposals[message_id] = plan_proposal
        if isinstance(plan_proposal, dict):
            self._run_js(
                f"updatePlanCard({json.dumps(plan_proposal)}, {json.dumps(plan_status)}, {json.dumps(message_id)});"
            )
        self._run_js(f"updatePlanStatusBanner({json.dumps(plan_status)});")
        self.pending_plan_apply = message_id is None and isinstance(plan_proposal, dict)
        self._update_plan_action_buttons()

    def _set_plan_confirm_enabled(self, enabled: bool):
        if not hasattr(self, "plan_confirm_btn"):
            return

        def _apply():
            self.plan_confirm_btn.setEnabled(enabled)

        QTimer.singleShot(0, _apply)

    def _update_plan_action_buttons(self):
        if not hasattr(self, "plan_action_container"):
            return
        status = self.last_plan_status
        has_plan = isinstance(self.last_plan_proposal, dict)

        show_confirm = has_plan and status in ("await_confirm", "await_plan_confirm")
        show_resume = status == "paused"
        show_exit = status in ("paused", "await_confirm", "await_plan_confirm", "collecting", "await_exit_confirm")
        visible = (show_confirm or show_resume or show_exit) and not self.chat_container.isHidden()

        def _apply():
            self.plan_confirm_btn.setVisible(show_confirm)
            self.plan_resume_btn.setVisible(show_resume)
            self.plan_exit_btn.setVisible(show_exit)
            self.plan_action_container.setVisible(visible)
            self.adjustSize()
            self.update_position(self.controller.pet_x, self.controller.pet_y)

        QTimer.singleShot(0, _apply)

    def _on_plan_confirm_clicked(self):
        self._set_plan_confirm_enabled(False)
        self.last_plan_status = None
        self._run_js("updatePlanStatusBanner(null);")
        self._update_plan_action_buttons()
        self._confirm_plan_update_async(self.last_plan_message_id)

    def _on_plan_resume_clicked(self):
        self._plan_session_action_async("resume")

    def _on_plan_exit_clicked(self):
        self.last_plan_status = None
        self._run_js("updatePlanStatusBanner(null);")
        self._update_plan_action_buttons()
        self._plan_session_action_async("exit")

    def _confirm_plan_update_async(self, message_id: str | None):
        plan_payload = None
        if message_id and message_id in self.plan_proposals:
            plan_payload = self.plan_proposals.get(message_id)
        if plan_payload is None and isinstance(self.last_plan_proposal, dict):
            plan_payload = self.last_plan_proposal
        if not self.task_id or not isinstance(plan_payload, dict):
            self._set_plan_confirm_enabled(True)
            return

        def _do_request():
            try:
                response = requests.post(
                    f"{self.api_base_url}/agent/task-plan/confirm",
                    json={"task_id": self.task_id, "plan": plan_payload},
                    timeout=10,
                )
                if response.ok:
                    self.last_plan_status = None
                    self._run_js(
                        f"updatePlanConfirmState(true, null, {json.dumps(message_id)}); updatePlanStatus(null, {json.dumps(message_id)});"
                    )
                    self._set_plan_confirm_enabled(False)
                    self._update_plan_action_buttons()
                else:
                    self._run_js(
                        f"updatePlanConfirmState(false, {json.dumps('请求失败')}, {json.dumps(message_id)});"
                    )
                    self._set_plan_confirm_enabled(True)
                    self._update_plan_action_buttons()
            except Exception as exc:
                self._run_js(
                    f"updatePlanConfirmState(false, {json.dumps(str(exc))}, {json.dumps(message_id)});"
                )
                self._set_plan_confirm_enabled(True)
                self._update_plan_action_buttons()

        threading.Thread(target=_do_request, daemon=True).start()

    def _plan_session_action_async(self, action: str):
        if not self.task_id:
            return
        if action == "exit":
            message_id = f"plan-action-{int(time.time() * 1000)}"
            self._run_js(
                f"startAssistantMessage({json.dumps(message_id)}); appendAssistantDelta({json.dumps(message_id)}, {json.dumps('好的，已结束学习计划规划。如需再规划，随时告诉我。')}); finishAssistantMessage({json.dumps(message_id)});"
            )

        def _do_request():
            try:
                response = requests.post(
                    f"{self.api_base_url}/agent/task-plan/session",
                    json={"task_id": self.task_id, "action": action},
                    timeout=10,
                )
                if response.ok:
                    data = response.json()
                    status = data.get("status")
                    self.last_plan_status = None if status == "idle" else status
                    self._run_js(f"updatePlanStatus({json.dumps(self.last_plan_status)});")
                    self._run_js(f"updatePlanStatusBanner({json.dumps(self.last_plan_status)});")
                    self._update_plan_action_buttons()
                    if action == "resume":
                        message_id = f"plan-action-{int(time.time() * 1000)}"
                        self._run_js(
                            f"startAssistantMessage({json.dumps(message_id)}); appendAssistantDelta({json.dumps(message_id)}, {json.dumps('好的，我们继续调整学习计划。请告诉我你想修改哪些内容。')}); finishAssistantMessage({json.dumps(message_id)});"
                        )
            except Exception:
                pass

        threading.Thread(target=_do_request, daemon=True).start()

    def mousePressEvent(self, event):
        self.reset_idle_timer() # 鼠标点击，重置待机
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False 
            self._drag_start_pos = event.globalPosition().toPoint() 
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            
            # ======= 【新增：立刻打断阿城当前动作，强制乖乖站立待命】 =======
            # 赋予 100 帧的持续时间，防止它在你看菜单时又突然跑掉
            self.controller.change_state("STAND", 100)
            # =============================================================
            
            menu = QMenu(self)

            new_task_action = menu.addAction("➕ 创建学习任务")
            new_task_action.triggered.connect(self._create_draft_task)
            menu.addSeparator()

            
            # ====== 修改这里：让任务菜单永远显示 ======
            task_menu = menu.addMenu("🗂 选择任务")
            tasks = self._refresh_tasks()
            
            if tasks:
                for task in tasks:
                    task_id = task.get("id")
                    title = task.get("title") or task_id
                    action = QAction(title, self)
                    action.setCheckable(True)
                    if task_id and task_id == self.task_id:
                        action.setChecked(True)
                    action.triggered.connect(
                        lambda checked=False, t_id=task_id, t_title=title: self._set_active_task(t_id, t_title)
                    )
                    task_menu.addAction(action)
            else:
                # 如果没拉取到数据，显示一个灰色的占位符，告诉你原因
                empty_action = QAction("后端未启动或暂无任务", self)
                empty_action.setEnabled(False) # 变成灰色不可点击状态
                task_menu.addAction(empty_action)
                
            menu.addSeparator()
            # ==========================================
            
            open_web_action = menu.addAction("🌐 打开 Web 面板")
            open_web_action.triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl("http://127.0.0.1:5173"))
            )
            menu.addSeparator() 
            menu.addAction("❌ 退出", QApplication.quit)
            menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            current_pos = event.globalPosition().toPoint()
            if not self._is_dragging:
                if (current_pos - self._drag_start_pos).manhattanLength() > 5:
                    self._is_dragging = True
                    self.controller.start_drag() 
            
            if self._is_dragging:
                new_win_pos = current_pos - self.drag_position
                self.controller.drag_to(new_win_pos.x() + self.pet_label.x(), new_win_pos.y() + self.pet_label.y()) 

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging:
                self.controller.end_drag() 
                self._is_dragging = False  

    def mouseDoubleClickEvent(self, event):
        self.reset_idle_timer() # 双击，重置待机
        
        # ====== 新增：冻结UI渲染，防止展开主面板时闪烁 ======
        self.setUpdatesEnabled(False)
        
        if self.chat_container.isHidden():
            self.chat_container.show(); self.input_container.show(); self.input_field.setFocus()
            self.controller.set_chatting(True) 
        else:
            self.chat_container.hide(); self.input_container.hide()
            self.controller.set_chatting(False) 
        
        self.adjustSize()
        self.update_position(self.controller.pet_x, self.controller.pet_y)
        self._update_plan_action_buttons()
        
        # 恢复UI渲染
        self.setUpdatesEnabled(True)
        # ===============================================

    def start_voice_recording(self):
        self.reset_idle_timer()
        self.input_field.setEnabled(False)
        self.input_field.setPlaceholderText("🎙️ 正在倾听，松开手发送...")
        self.voice_btn.setText("👄")
        
        self.audio_file_path = os.path.join(BASE_DIR, "temp_audio.wav")
        self.audio_recorder = AudioRecorder(self.audio_file_path)
        self.audio_recorder.start()

    def stop_voice_recording(self):
        self.reset_idle_timer()
        self.voice_btn.setText("🎤")
        if hasattr(self, 'audio_recorder'):
            self.audio_recorder.stop()
            self.audio_recorder.wait()
        
        self.input_field.setPlaceholderText("正在上传语音让 Tutor 思考中... 🧠")
        self._ensure_task_for_send()
        
        # ====== 核心修改：触发前端生成包含语音占位符的真实用户卡片 ======
        self.add_bubble("🎤 语音输入...", True)
        # ==============================================================
        
        self.controller.change_state("THINKING", 9999) 
        
        self.worker = VoiceAgentWorker(
            self.api_base_url,
            self.session_id,
            self.topic,
            self.audio_file_path,
            task_id=self.task_id,
        )
        self.worker.session_ready.connect(self._update_session_id)
        self.worker.response_ready.connect(self.handle_response)
        self.worker.start()

    def send_message(self):
        self.reset_idle_timer()
        text = self.input_field.text()
        if not text: return
        self.input_field.clear()
        self._ensure_task_for_send()
        self.input_field.setEnabled(False)
        self.input_field.setPlaceholderText("Tutor 正在通过 API 思考中... 🧠")
        
        # ====== 核心修改：将用户的真实问题发送给前端，生成一张新卡片 ======
        self.add_bubble(text, True)
        # =================================================================
        
        self.controller.change_state("THINKING", 9999) 
        
        self.worker = AgentWorker(self.api_base_url, self.session_id, self.topic, text, task_id=self.task_id)
        self.worker.session_ready.connect(self._update_session_id)
        self.worker.stream_started.connect(self.start_stream_bubble)
        self.worker.chunk_ready.connect(self.append_stream_bubble)
        
        # ====== 新增：重新绑定大模型意图和节点状态信号 ======
        self.worker.node_changed.connect(self.update_node_status)
        self.worker.intent_changed.connect(self.update_intent_status)
        self.worker.plan_ready.connect(self.update_plan_proposal)
        # ====================================================
        
        self.worker.response_ready.connect(self.handle_response)
        self.worker.start()

    def handle_response(self, text, is_concluded):
        self.input_field.setEnabled(True)
        self.input_field.setPlaceholderText("想问点什么？按回车发送...")
        self.input_field.setFocus()
        if self.active_stream_message_id:
            self.finish_stream_bubble(self.active_stream_message_id)
        elif text:
            self.add_bubble(text, False)
        if self.pending_plan_apply and isinstance(self.last_plan_proposal, dict):
            self._run_js(
                f"updatePlanCard({json.dumps(self.last_plan_proposal)}, {json.dumps(self.last_plan_status)}, null);"
            )
            self._run_js(f"updatePlanStatusBanner({json.dumps(self.last_plan_status)});")
            self.pending_plan_apply = False
        self.controller.change_state("STAND", 20)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL) 
    app = QApplication(sys.argv)
    pet = ChatTutorPet()
    pet.show()
    sys.exit(app.exec())
