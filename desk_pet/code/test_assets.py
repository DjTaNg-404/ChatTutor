import sys
import os
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QGridLayout
from PyQt6.QtGui import QMovie, QPainter
from PyQt6.QtCore import Qt

# 导入你写好的物理引擎大脑（不需要修改它任何代码！）
from pet_controller import PetController

# ================= 1. 自定义画板 (支持水平翻转) =================
class PetLabel(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_flipped = False
        self._movie = None

    def setMovie(self, movie):
        if self._movie:
            self._movie.frameChanged.disconnect(self.update)
        self._movie = movie
        if self._movie:
            self._movie.frameChanged.connect(self.update)

    def movie(self):
        return self._movie

    def set_flipped(self, flipped):
        if self.is_flipped != flipped:
            self.is_flipped = flipped
            self.update()

    def paintEvent(self, event):
        if not self._movie or not self._movie.currentPixmap():
            return
        painter = QPainter(self)
        pixmap = self._movie.currentPixmap()
        
        x = int((self.width() - pixmap.width()) / 2)
        y = int((self.height() - pixmap.height()) / 2)
        
        if self.is_flipped:
            painter.translate(self.width(), 0)
            painter.scale(-1, 1)
            
        painter.drawPixmap(x, y, pixmap)


# ================= 2. 真实的透明测试桌宠 =================
class DebugPetWindow(QWidget):
    def __init__(self):
        super().__init__()
        # 设置窗口为透明、无边框、永远置顶
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.pet_width = 150
        self.pet_height = 150
        self.resize(self.pet_width, self.pet_height)
        
        # 画面显示标签
        self.label = PetLabel(self)
        self.label.resize(self.pet_width, self.pet_height)
        
        # 加载动图
        self.assets = {}
        self.init_assets()
        
        # 初始化桌宠大脑
        screen_rect = QApplication.primaryScreen().availableGeometry()
        self.controller = PetController(screen_rect, self.pet_width, self.pet_height, int(self.winId()))
        
        # 绑定大脑的信号
        self.controller.position_changed.connect(self.move)
        self.controller.appearance_changed.connect(self.update_appearance)
        self.controller.direction_changed.connect(self.label.set_flipped)

    def init_assets(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img_dir = os.path.join(base_dir, "img")
        
        actions = ["stand", "walk1", "walk2", "sit", "sitting", "standing", 
                   "say_hi1", "say_hi2", "thinking", "catching", "felling", 
                   "fell", "getup", "jump", "sleep", "reading"]
        for act in actions:
            path = os.path.join(img_dir, f"{act}.gif")
            if os.path.exists(path):
                movie = QMovie(path)
                movie.setScaledSize(self.size())
                self.assets[act] = movie
            else:
                print(f"⚠️ 找不到测试所需文件: {path}")

    def update_appearance(self, action_name):
        movie = self.assets.get(action_name)
        if movie:
            if self.label.movie():
                self.label.movie().stop()
            self.label.setMovie(movie)
            movie.start()

    # 简易拖拽实现
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.controller.start_drag()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            # 拖拽时让鼠标在桌宠中心
            self.controller.drag_to(global_pos.x() - self.width()/2, global_pos.y() - self.height()/2)
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.controller.end_drag()


# ================= 3. 独立遥控器面板 =================
class RemoteControlPanel(QWidget):
    def __init__(self, pet_window):
        super().__init__()
        self.pet_window = pet_window
        self.setWindowTitle("🚀 桌宠动作强制遥控器")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint) # 面板也置顶
        
        layout = QGridLayout(self)
        
        actions = [
            "STAND", "WALK", "SIT", "SITTING", "STANDING", 
            "SAY_HI1", "SAY_HI2", "THINKING", "READING",
            "JUMP", "FALLING", "FELL", "GETUP", "SLEEP"
        ]
        
        row, col = 0, 0
        for act in actions:
            btn = QPushButton(act)
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda checked, a=act: self.force_action(a))
            layout.addWidget(btn, row, col)
            
            col += 1
            if col > 2: # 每行放3个按钮
                col = 0
                row += 1

    def force_action(self, action_name):
        ctrl = self.pet_window.controller
        
        # 强制切换状态，并给足表现时间 (100帧 = 5秒)
        ctrl.change_state(action_name, 100)
        
        # 赋予特殊动作的物理参数，测试真实物理表现
        if action_name == "WALK":
            ctrl.vx = 4.0  # 强制向右走
            ctrl.vy = 0.0
        elif action_name == "JUMP":
            ctrl.vx = 0.0
            ctrl.vy = -20.0 # 给一个向上的初速度，测试抛物线
        elif action_name in ["FALLING", "STAND", "SIT", "SLEEP", "READING", "THINKING"]:
            ctrl.vx = 0.0
            ctrl.vy = 0.0


# ================= 启动程序 =================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 1. 呼出测试桌宠
    pet = DebugPetWindow()
    pet.show()
    
    # 2. 呼出遥控器面板
    remote = RemoteControlPanel(pet)
    remote.show()
    # 把遥控器放在屏幕左上角，不挡视线
    remote.move(50, 50)
    
    sys.exit(app.exec())