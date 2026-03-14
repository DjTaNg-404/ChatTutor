# desk_pet/code/main.py
import sys
import os
import signal 
import json
from datetime import datetime
import requests

# ======= 【核心修复：禁用 Chromium 硬件加速，防止透明窗口渲染崩溃】 =======
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing --log-level=3"
# ======================================================================================

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QLabel, QMenu, QPushButton)
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent, QUrl
from PyQt6.QtGui import QMovie, QFont, QAction, QPixmap, QPainter, QDesktopServices
from PyQt6.QtWebEngineWidgets import QWebEngineView

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
        self._auto_select_default_task()
        self.init_controller()  
        self.active_stream_message_id = None

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
        
        self.layout.addWidget(self.chat_container) 
        self.layout.addWidget(self.input_container) 
        self.layout.addWidget(self.pet_label, alignment=Qt.AlignmentFlag.AlignHCenter) 

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
        self.session_id = "pet_session_1"
        self.topic = "General"

    def _refresh_tasks(self):
        try:
            response = requests.get(f"{self.api_base_url}/tasks", timeout=5)
            response.raise_for_status()
            return response.json().get("tasks", [])
        except Exception:
            return []

    def _set_active_task(self, task_id, title):
        self.task_id = task_id
        self.task_title = title
        self.topic = title or "General"
        timestamp = datetime.now().strftime("%Y%m%d__%H%M%S")
        self.session_id = f"{task_id}__{timestamp}"

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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False 
            self._drag_start_pos = event.globalPosition().toPoint() 
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            tasks = self._refresh_tasks()
            if tasks:
                task_menu = menu.addMenu("🗂 选择任务")
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
                menu.addSeparator()
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
        if self.chat_container.isHidden():
            self.chat_container.show(); self.input_container.show(); self.input_field.setFocus()
            self.controller.set_chatting(True) 
        else:
            self.chat_container.hide(); self.input_container.hide()
            self.controller.set_chatting(False) 
        
        self.adjustSize()
        self.update_position(self.controller.pet_x, self.controller.pet_y)

    def start_voice_recording(self):
        self.input_field.setEnabled(False)
        self.input_field.setPlaceholderText("🎙️ 正在倾听，松开手发送...")
        self.voice_btn.setText("👄")
        
        self.audio_file_path = os.path.join(BASE_DIR, "temp_audio.wav")
        self.audio_recorder = AudioRecorder(self.audio_file_path)
        self.audio_recorder.start()

    def stop_voice_recording(self):
        self.voice_btn.setText("🎤")
        if hasattr(self, 'audio_recorder'):
            self.audio_recorder.stop()
            self.audio_recorder.wait()
        
        self.input_field.setPlaceholderText("正在上传语音让 Tutor 思考中... 🧠")
        
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
        self.worker.response_ready.connect(self.handle_response)
        self.worker.start()

    def send_message(self):
        text = self.input_field.text()
        if not text: return
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.input_field.setPlaceholderText("Tutor 正在通过 API 思考中... 🧠")
        
        # ====== 核心修改：将用户的真实问题发送给前端，生成一张新卡片 ======
        self.add_bubble(text, True)
        # =================================================================
        
        self.controller.change_state("THINKING", 9999) 
        
        self.worker = AgentWorker(self.api_base_url, self.session_id, self.topic, text, task_id=self.task_id)
        self.worker.stream_started.connect(self.start_stream_bubble)
        self.worker.chunk_ready.connect(self.append_stream_bubble)
        
        # ====== 新增：重新绑定大模型意图和节点状态信号 ======
        self.worker.node_changed.connect(self.update_node_status)
        self.worker.intent_changed.connect(self.update_intent_status)
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
        self.controller.change_state("STAND", 20)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL) 
    app = QApplication(sys.argv)
    pet = ChatTutorPet()
    pet.show()
    sys.exit(app.exec())