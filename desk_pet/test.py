import sys
import os
import signal 
import requests
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLineEdit, QLabel
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QTimer, QEvent
from PyQt6.QtGui import QMovie, QFont

# ================= 核心工作线程 =================
class AgentWorker(QThread):
    """负责核心学习逻辑的线程 (调用 FastAPI /chat)"""
    response_ready = pyqtSignal(str, bool)
    
    def __init__(self, api_base_url, session_id, topic, user_input):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")
        self.session_id = session_id
        self.topic = topic
        self.user_input = user_input

    def run(self):
        try:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={
                    "session_id": self.session_id,
                    "message": self.user_input,
                    "topic": self.topic,
                },
                timeout=30,
            )

            if response.status_code != 200:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                self.response_ready.emit(f"接口调用失败（{response.status_code}）：{detail}", False)
                return

            data = response.json()
            reply = data.get("reply", "抱歉，我暂时没有生成回复。")
            is_concluded = bool(data.get("is_concluded", False))
            self.response_ready.emit(reply, is_concluded)
        except requests.RequestException as e:
            self.response_ready.emit(f"网络请求失败：{str(e)}", False)
        except Exception as e:
            self.response_ready.emit(f"处理响应时出错：{str(e)}", False)


# ================= 桌面宠物 UI =================
class ChatTutorPet(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
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
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(252, 252, 255, 230);
                border: 1px solid rgba(200, 200, 220, 150);
                border-radius: 12px;
                padding: 12px;
                color: #333333;
                font-size: 13px;
            }
        """)
        self.chat_display.setFixedHeight(120) 
        self.chat_display.installEventFilter(self) 
        self.chat_display.hide()

        self.pet_label = QLabel(self)
        gif_path = os.path.join(self.base_dir, "AC.gif")
        self.pet_movie = QMovie(gif_path)
        self.pet_label.setMovie(self.pet_movie)
        self.pet_movie.start()
        self.pet_label.setScaledContents(True)
        self.pet_label.setFixedSize(150, 150)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("想问点什么？按回车发送...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 240);
                border: 2px solid #E0E0E0;
                border-radius: 15px;
                padding: 6px 14px;
                color: #333333;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #4A90E2;
                background-color: #FFFFFF;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.hide()
        
        self.layout.addWidget(self.chat_display) 
        self.layout.addWidget(self.pet_label, alignment=Qt.AlignmentFlag.AlignHCenter) 
        self.layout.addWidget(self.input_field) 

        self.is_thinking = False
        self.think_timer = QTimer(self)
        self.think_timer.timeout.connect(self.animate_thinking)
        
    def init_agent(self):
        self.api_base_url = os.getenv("CHAT_API_BASE_URL", "http://127.0.0.1:8000/api/v1")
        self.session_id = "pet_session_1"
        self.topic = "General"

    def eventFilter(self, obj, event):
        if obj == self.chat_display:
            if event.type() == QEvent.Type.Enter:
                self.chat_display.setFixedHeight(400) 
            elif event.type() == QEvent.Type.Leave:
                self.chat_display.setFixedHeight(120) 
        return super().eventFilter(obj, event)

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.chat_display.isHidden():
            self.chat_display.show()
            self.input_field.show()
            self.input_field.setFocus()
        else:
            self.chat_display.hide()
            self.input_field.hide()

    # ================= 常规对话与思考动画逻辑 =================
    def animate_thinking(self):
        if self.pet_movie.state() != QMovie.MovieState.Running:
            self.pet_movie.start()

    def send_message(self):
        text = self.input_field.text()
        if not text: return
        
        user_html = f"<div style='margin-bottom: 5px;'><span style='color: #4A90E2; font-weight: bold;'>👤 You: </span><span style='color: #333;'>{text}</span></div>"
        self.chat_display.append(user_html)
        self.input_field.clear()
        
        self.is_thinking = True
        self.input_field.setEnabled(False) 
        self.input_field.setPlaceholderText("Tutor 正在飞速查阅和思考中... 🧠")
        self.think_timer.start(400) 
        
        self.worker = AgentWorker(self.api_base_url, self.session_id, self.topic, text)
        self.worker.response_ready.connect(self.handle_response)
        self.worker.start()

    def handle_response(self, text, is_concluded):
        self.is_thinking = False
        self.think_timer.stop() 
        
        self.input_field.setEnabled(True) 
        self.input_field.setPlaceholderText("想问点什么？按回车发送...") 
        self.input_field.setFocus() 
        
        formatted_text = text.replace('\n', '<br>')
        ai_html = f"<div style='margin-bottom: 15px;'><span style='color: #E67E22; font-weight: bold;'>🤖 Tutor: </span><span style='color: #444; line-height: 1.5;'>{formatted_text}</span></div>"
        self.chat_display.append(ai_html)

        if is_concluded:
            self.input_field.setEnabled(False)
            self.input_field.setPlaceholderText("会话已结束，请重启应用开启新会话。")


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None) 
    
    pet = ChatTutorPet()
    pet.show()
    sys.exit(app.exec())