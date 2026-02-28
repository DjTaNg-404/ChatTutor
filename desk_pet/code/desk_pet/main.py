# desk_pet/code/main.py
import sys
import os
import signal 
import json
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QLabel, QMenu, QPushButton)
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent
from PyQt6.QtGui import QMovie, QFont, QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView

# 导入封装好的模块
from config import HTML_TEMPLATE, BASE_DIR
# 注意这里增加了对 AudioRecorder 和 VoiceAgentWorker 的导入
from text_worker import AgentWorker
from voice_worker import AudioRecorder, VoiceAgentWorker

class ChatTutorPet(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.current_theme = "adult"        
        self.current_pet_state = "sleep"    
        
        self.init_ui()
        self.init_agent()
        
    def init_ui(self):
        font = QFont("Microsoft YaHei", 10)
        QApplication.setFont(font)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(12) 
        
        # 聊天容器
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

        # 桌宠动图
        self.pet_label = QLabel(self)
        self.gif_size = QSize(150, 150) 
        self.load_theme_gifs()
        self.pet_label.setFixedSize(self.gif_size)
        
        # 输入框
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("想问点什么？按回车发送...")
        # 为了给右侧的语音按钮腾出空间，稍微缩小输入框的最小宽度
        self.input_field.setMinimumWidth(290)
        self.input_field.setStyleSheet("background-color: rgba(255, 255, 255, 240); border: 2px solid #E0E0E0; border-radius: 15px; padding: 6px 14px;")
        self.input_field.returnPressed.connect(self.send_message)
        
        # === 【新增 UI】麦克风按钮 ===
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setFixedSize(36, 36)
        self.voice_btn.setStyleSheet("""
            QPushButton { 
                background-color: #ffffff; 
                border: 2px solid #E0E0E0; 
                border-radius: 18px; 
                font-size: 16px; 
            } 
            QPushButton:pressed { 
                background-color: #e0e0e0; 
            }
        """)
        # 绑定按下(开始录音)和松开(停止录音并发送)事件
        self.voice_btn.pressed.connect(self.start_voice_recording)
        self.voice_btn.released.connect(self.stop_voice_recording)
        
        # 创建一个水平布局把 输入框 和 按钮 并排放在一起
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.voice_btn)
        
        # 初始状态隐藏他们的大容器
        self.input_container = QWidget()
        self.input_container.setLayout(input_layout)
        self.input_container.hide()
        
        self.layout.addWidget(self.chat_container) 
        self.layout.addWidget(self.pet_label, alignment=Qt.AlignmentFlag.AlignHCenter) 
        # 这里把原本的 input_field 改成组合了麦克风的 input_container
        self.layout.addWidget(self.input_container) 
        
    def init_agent(self):
        self.api_base_url = "http://127.0.0.1:8000/api/v1"
        self.session_id = "pet_session_1"
        self.topic = "General"

    def load_theme_gifs(self):
        if hasattr(self, 'movie_sleep'): self.movie_sleep.stop()
        if hasattr(self, 'movie_work'): self.movie_work.stop()

        f_sleep, f_work = ("Work.gif", "Sleep.gif") if self.current_theme == "high_school" else ("Sleep.gif", "Work.gif")
        
        # 使用 normpath 确保 Windows 下路径斜杠的绝对一致性
        path_sleep = os.path.normpath(os.path.join(BASE_DIR, "Figure", self.current_theme, f_sleep))
        path_work = os.path.normpath(os.path.join(BASE_DIR, "Figure", self.current_theme, f_work))

        # 防止找不到文件变透明幽灵的终极保险
        if not os.path.exists(path_sleep) or not os.path.exists(path_work):
            print(f"\n❌ [路径错误] 找不到动图文件！\n尝试寻找: {path_sleep}")
            return

        self.movie_sleep = QMovie(path_sleep)
        self.movie_sleep.setScaledSize(self.gif_size)
        self.movie_work = QMovie(path_work)
        self.movie_work.setScaledSize(self.gif_size)
        
        self.set_pet_state(self.current_pet_state)

    def set_theme(self, new_theme):
        self.current_theme = new_theme
        self.load_theme_gifs()

    def set_pet_state(self, state):
        self.current_pet_state = state
        self.pet_label.setMovie(self.movie_sleep if state == "sleep" else self.movie_work)
        (self.movie_work if state == "sleep" else self.movie_sleep).stop()
        (self.movie_sleep if state == "sleep" else self.movie_work).start()

    def eventFilter(self, obj, event):
        if obj == self.chat_container:
            if event.type() == QEvent.Type.Enter:
                old_center = self.pet_label.mapToGlobal(self.pet_label.rect().center())
                self.chat_container.setFixedHeight(400) 
                self.adjustSize()
                self.move(self.pos() - (self.pet_label.mapToGlobal(self.pet_label.rect().center()) - old_center))
                self.web_view.page().runJavaScript("setHover(true);")
            elif event.type() == QEvent.Type.Leave:
                old_center = self.pet_label.mapToGlobal(self.pet_label.rect().center())
                self.chat_container.setFixedHeight(120) 
                self.adjustSize()
                self.move(self.pos() - (self.pet_label.mapToGlobal(self.pet_label.rect().center()) - old_center))
                self.web_view.page().runJavaScript("setHover(false);")
        return super().eventFilter(obj, event)

    def add_bubble(self, text, is_user=False):
        js_code = f"addMessage({json.dumps(text)}, {'true' if is_user else 'false'});"
        self.web_view.page().runJavaScript(js_code)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            t_info = {"adult": "大学生", "high_school": "中学生", "elementary_school": "小学生"}
            for k, v in t_info.items():
                if k != self.current_theme:
                    a = QAction(f"切换为{v}形象", self)
                    a.triggered.connect(lambda checked, tk=k: self.set_theme(tk))
                    menu.addAction(a)
            menu.addSeparator()
            menu.addAction("退出", self.close)
            menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def mouseDoubleClickEvent(self, event):
        old_center = self.pet_label.mapToGlobal(self.pet_label.rect().center())
        if self.chat_container.isHidden():
            # 显示的时候显示大容器 container
            self.chat_container.show(); self.input_container.show(); self.input_field.setFocus()
            self.set_pet_state("work")
        else:
            # 隐藏的时候隐藏大容器 container
            self.chat_container.hide(); self.input_container.hide()
            self.set_pet_state("sleep")
        self.adjustSize()
        self.move(self.pos() - (self.pet_label.mapToGlobal(self.pet_label.rect().center()) - old_center))

    # ================= 语音交互逻辑 =================
    def start_voice_recording(self):
        self.input_field.setEnabled(False)
        self.input_field.setPlaceholderText("🎙️ 正在倾听，松开手发送...")
        self.voice_btn.setText("👄")
        
        # 将录音文件保存在 desk_pet 目录下
        self.audio_file_path = os.path.join(BASE_DIR, "temp_audio.wav")
        
        # 开启后台录音线程
        self.audio_recorder = AudioRecorder(self.audio_file_path)
        self.audio_recorder.start()

    def stop_voice_recording(self):
        self.voice_btn.setText("🎤")
        
        # 叫停录音线程并等待写入完成
        if hasattr(self, 'audio_recorder'):
            self.audio_recorder.stop()
            self.audio_recorder.wait()
        
        self.input_field.setPlaceholderText("正在上传语音让 Tutor 思考中... 🧠")
        
        # 气泡提示
        self.add_bubble("🎵 [发送了一条语音]", True)
        
        # 启动语音上传线程
        self.worker = VoiceAgentWorker(self.api_base_url, self.session_id, self.topic, self.audio_file_path)
        self.worker.response_ready.connect(self.handle_response)
        self.worker.start()

    # ================= 文本交互逻辑 =================
    def send_message(self):
        text = self.input_field.text()
        if not text: return
        self.add_bubble(text, True); self.input_field.clear()
        self.input_field.setEnabled(False); self.input_field.setPlaceholderText("Tutor 正在通过 API 思考中... 🧠")
        self.worker = AgentWorker(self.api_base_url, self.session_id, self.topic, text)
        self.worker.response_ready.connect(self.handle_response); self.worker.start()

    def handle_response(self, text, is_concluded):
        self.input_field.setEnabled(True); self.input_field.setPlaceholderText("想问点什么？按回车发送...")
        self.input_field.setFocus(); self.add_bubble(text, False)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    pet = ChatTutorPet()
    pet.show()
    sys.exit(app.exec())