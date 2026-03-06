# desk_pet/code/main.py
import sys
import os
import signal 
import json
if sys.platform.startswith("win"):
    try:
        # Ensure Windows ICU DLLs take precedence over Anaconda's older ICU.
        os.add_dll_directory(r"C:\Windows\System32")
    except Exception:
        pass
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QLabel, QMenu, QPushButton)
# 引入了 QUrl
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent, QUrl
# 引入了 QPainter 和 QDesktopServices
from PyQt6.QtGui import QMovie, QFont, QAction, QPixmap, QPainter, QDesktopServices
from PyQt6.QtWebEngineWidgets import QWebEngineView

# 导入封装好的模块
from config import HTML_TEMPLATE, BASE_DIR
from text_worker import AgentWorker
from voice_worker import AudioRecorder, VoiceAgentWorker

# === 导入抽离出来的物理引擎与状态大脑 ===
from pet_controller import PetController


# ================= 新增：支持动态水平翻转的自制画板 =================
class PetLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_flipped = False

    def set_flipped(self, flipped):
        if self.is_flipped != flipped:
            self.is_flipped = flipped
            self.update() # 强制通知系统重新绘制这一帧

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = None
        
        # 提取当前的图片帧
        if self.movie() and self.movie().currentPixmap() and not self.movie().currentPixmap().isNull():
            pixmap = self.movie().currentPixmap()
        elif self.pixmap() and not self.pixmap().isNull():
            pixmap = self.pixmap()
            
        if pixmap:
            x = int((self.width() - pixmap.width()) / 2)
            y = int((self.height() - pixmap.height()) / 2)
            
            # 核心黑科技：镜像翻转整个画笔坐标系！
            if self.is_flipped:
                painter.translate(self.width(), 0)
                painter.scale(-1, 1)
                
            painter.drawPixmap(x, y, pixmap)
# ====================================================================


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
        self.init_controller()  
        self.active_stream_message_id = None

    def init_ui(self):
        font = QFont("Microsoft YaHei", 10)
        QApplication.setFont(font)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(12) 
        
        self.chat_container = QWidget()
        self.chat_container.setFixedHeight(120)
        self.chat_container.setMinimumWidth(340)
        self.chat_container.setStyleSheet("background-color: rgba(245, 245, 247, 230); border: 1px solid rgba(200, 200, 220, 150); border-radius: 12px;")
        self.chat_container.installEventFilter(self)
        
        container_layout = QVBoxLayout(self.chat_container)
        container_layout.setContentsMargins(4, 4, 4, 4)
        
        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.web_view.setHtml(HTML_TEMPLATE)
        container_layout.addWidget(self.web_view)
        self.chat_container.hide()

        # 【关键修改】：使用我们自制的 PetLabel 替换掉原本的 QLabel
        self.pet_label = PetLabel(self)
        self.pet_label.setFixedSize(self.gif_size)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("想问点什么？按回车发送...")
        self.input_field.setMinimumWidth(290)
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
        
    def init_agent(self):
        self.api_base_url = "http://127.0.0.1:8000/api/v1"
        self.session_id = "pet_session_1"
        self.topic = "General"

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
        
        # 【关键修改】：把大脑的转向信号连接到自制画板上
        self.controller.direction_changed.connect(self.pet_label.set_flipped)
        
        self.controller.drag_to(self.x() + self.pet_label.x(), self.y() + self.pet_label.y())
        self.controller.change_state("STAND")

    def update_position(self, pet_x, pet_y):
        win_x = pet_x - self.pet_label.x()
        win_y = pet_y - self.pet_label.y()
        self.move(int(win_x), int(win_y))

    def eventFilter(self, obj, event):
        if obj == self.chat_container:
            if event.type() == QEvent.Type.Enter:
                self.chat_container.setFixedHeight(400) 
                self.adjustSize()
                self.update_position(self.controller.pet_x, self.controller.pet_y)
                self.web_view.page().runJavaScript("setHover(true);")
            elif event.type() == QEvent.Type.Leave:
                self.chat_container.setFixedHeight(120) 
                self.adjustSize()
                self.update_position(self.controller.pet_x, self.controller.pet_y)
                self.web_view.page().runJavaScript("setHover(false);")
        return super().eventFilter(obj, event)

    def add_bubble(self, text, is_user=False):
        js_code = f"addMessage({json.dumps(text)}, {'true' if is_user else 'false'});"
        self.web_view.page().runJavaScript(js_code)

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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False 
            self._drag_start_pos = event.globalPosition().toPoint() 
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            # ================= 新增：打开 Web 面板 =================
            open_web_action = menu.addAction("🌐 打开 Web 面板")
            open_web_action.triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl("http://127.0.0.1:5173"))
            )
            menu.addSeparator() # 分割线
            # =======================================================
            
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
        self.add_bubble("🎵 [发送了一条语音]", True)
        
        self.controller.change_state("THINKING", 9999) 
        
        self.worker = VoiceAgentWorker(self.api_base_url, self.session_id, self.topic, self.audio_file_path)
        self.worker.response_ready.connect(self.handle_response)
        self.worker.start()

    def send_message(self):
        text = self.input_field.text()
        if not text: return
        self.add_bubble(text, True); self.input_field.clear()
        self.input_field.setEnabled(False); self.input_field.setPlaceholderText("Tutor 正在通过 API 思考中... 🧠")
        
        self.controller.change_state("THINKING", 9999) 
        
        self.worker = AgentWorker(self.api_base_url, self.session_id, self.topic, text)
        self.worker.stream_started.connect(self.start_stream_bubble)
        self.worker.chunk_ready.connect(self.append_stream_bubble)
        self.worker.stream_finished.connect(self.finish_stream_bubble)
        self.worker.response_ready.connect(self.handle_response); self.worker.start()

    def handle_response(self, text, is_concluded):
        self.input_field.setEnabled(True); self.input_field.setPlaceholderText("想问点什么？按回车发送...")
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
