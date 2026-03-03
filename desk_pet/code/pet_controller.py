import sys
import random
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# ================= 跨平台系统依赖注入 =================
if sys.platform == "win32":
    import ctypes
    from ctypes.wintypes import RECT
elif sys.platform == "darwin":
    try:
        import Quartz
        from AppKit import NSWorkspace
    except ImportError:
        print("缺少 macOS 依赖，请在终端运行: pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa")

# 统一的边界框类，抹平 Windows(RECT) 和 macOS(字典) 的数据格式差异
class UniversalRect:
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
# ====================================================

class PetController(QObject):
    position_changed = pyqtSignal(int, int)  
    appearance_changed = pyqtSignal(str)     
    direction_changed = pyqtSignal(bool) 

    def __init__(self, screen_rect, pet_width, pet_height, win_id):
        super().__init__()
        self.screen_rect = screen_rect
        self.pet_width = pet_width
        self.pet_height = pet_height
        self.win_id = win_id
        
        self.state = "STAND"      
        self.state_timer = 0      
        self.vx = 0.0             
        self.vy = 0.0             
        self.pet_x = 500.0        
        self.pet_y = 300.0        
        self.walk_frame = 0       
        
        self.is_flipped = False  
        
        # ================= 动作逻辑锁 =================
        self.sit_has_thought = False # 坐下时是否思考过
        self.stand_has_acted = False # 站立时是否做过动作 (walk, sleep, say_hi1, reading)
        # ==============================================
        
        # ================= 聊天冻结标记 =================
        self.is_chatting = False
        # ==============================================

        # ================= 修复幽灵坐标：缓存窗口句柄 =================
        self.last_active_hwnd = None  
        self.last_active_win_rect = None 
        # ==============================================================
        
        self.floor_y = self.screen_rect.height() - self.pet_height
        
        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self.game_loop)
        self.game_timer.start(50)

    def start_drag(self):
        self.change_state("DRAGGED")
        
    def drag_to(self, x, y):
        self.pet_x, self.pet_y = float(x), float(y)
        self.position_changed.emit(int(self.pet_x), int(self.pet_y))
        
    def end_drag(self):
        self.vx, self.vy = 0.0, 0.0
        # 如果正在聊天，松手时保持悬浮思考；否则触发物理掉落
        if self.is_chatting:
            self.change_state("THINKING", 9999) 
        else:
            self.change_state("FALLING")
        
    def set_chatting(self, is_chatting):
        self.is_chatting = is_chatting
        if is_chatting:
            self.vx, self.vy = 0.0, 0.0
            self.change_state("THINKING", 9999)
        else:
            # 退出聊天，恢复物理判定，它会自动掉下去
            self.change_state("STAND", 20)

    def get_active_window_rect(self):
        # ================= Windows 逻辑 =================
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            
            if hwnd == self.win_id:
                hwnd = self.last_active_hwnd
                
            if not hwnd or hwnd == 0:
                self.last_active_hwnd = None
                self.last_active_win_rect = None
                return None
                
            if user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
                self.last_active_hwnd = None
                self.last_active_win_rect = None
                return None
                
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            c_name = class_name.value
            
            if hwnd == user32.GetDesktopWindow() or c_name in ["WorkerW", "Progman", "Shell_TrayWnd"]:
                self.last_active_hwnd = None
                self.last_active_win_rect = None
                return None

            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            
            if (rect.right - rect.left) >= self.screen_rect.width() - 20 and (rect.bottom - rect.top) >= self.screen_rect.height() - 20:
                self.last_active_hwnd = None
                self.last_active_win_rect = None
                return None 
                
            self.last_active_hwnd = hwnd
            self.last_active_win_rect = UniversalRect(rect.left, rect.top, rect.right, rect.bottom)
            return self.last_active_win_rect

        # ================= macOS 逻辑 =================
        elif sys.platform == "darwin":
            try:
                active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
                if not active_app:
                    return None
                    
                pid = active_app.processIdentifier()
                
                # 获取屏幕上可见的窗口信息
                options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
                window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
                
                for window in window_list:
                    # 匹配当前活跃应用的 PID
                    if window.get('kCGWindowOwnerPID') == pid:
                        # 过滤掉透明/隐藏的幽灵窗口
                        if window.get('kCGWindowAlpha', 1.0) == 0.0:
                            continue
                            
                        bounds = window.get('kCGWindowBounds')
                        if bounds:
                            left = bounds['X']
                            top = bounds['Y']
                            right = left + bounds['Width']
                            bottom = top + bounds['Height']
                            
                            # 过滤全屏窗口
                            if bounds['Width'] >= self.screen_rect.width() - 20 and bounds['Height'] >= self.screen_rect.height() - 20:
                                return None
                                
                            return UniversalRect(left, top, right, bottom)
                return None
            except Exception as e:
                print(f"macOS 窗口获取失败: {e}")
                return None

        return None

    def game_loop(self):
        if self.state == "DRAGGED": 
            return 
            
        # ================= 核心冻结逻辑 =================
        if self.is_chatting:
            self.position_changed.emit(int(self.pet_x), int(self.pet_y))
            return
        # ================================================
            
        self.pet_x += self.vx
        self.pet_y += self.vy
        
        active_win = self.get_active_window_rect()
        target_floor_y = self.floor_y

        on_window = False
        if active_win and self.state != "DRAGGED":
            pet_center_x = self.pet_x + self.pet_width / 2
            if active_win.left <= pet_center_x <= active_win.right:
                window_top_y = active_win.top - self.pet_height + 25 
                
                if self.vy >= 0:
                    if self.pet_y <= window_top_y + 80:
                        target_floor_y = window_top_y
                        on_window = True
                else:
                    if self.pet_y <= window_top_y:
                        target_floor_y = window_top_y
                        on_window = True

        if self.pet_y < target_floor_y - 5:  
            self.vy += 2.0  
            if self.state not in ["FALLING", "FELL", "JUMP"]: 
                self.change_state("FALLING")
        elif self.pet_y < target_floor_y:
            self.pet_y = target_floor_y
            self.vy = 0
            if self.state == "FALLING":
                self.change_state("FELL")
            elif self.state == "JUMP": 
                self.change_state("STAND", random.randint(100, 200))
        else:
            self.pet_y = target_floor_y
            self.vy = 0
            if self.state == "FALLING":
                self.change_state("FELL")
            elif self.state == "JUMP": 
                self.change_state("STAND", random.randint(100, 200))

        if self.pet_x < 0: 
            self.pet_x = 0
            self.vx = abs(self.vx)  
        elif self.pet_x > self.screen_rect.width() - self.pet_width: 
            self.pet_x = self.screen_rect.width() - self.pet_width
            self.vx = -abs(self.vx) 

        new_flipped = self.is_flipped
        
        if self.vx > 0:
            new_flipped = True   
        elif self.vx < 0:
            new_flipped = False  
        else:
            screen_center = self.screen_rect.width() / 2
            pet_center = self.pet_x + self.pet_width / 2
            new_flipped = (pet_center < screen_center)
            
        if new_flipped != self.is_flipped:
            self.is_flipped = new_flipped
            self.direction_changed.emit(self.is_flipped)

        self.position_changed.emit(int(self.pet_x), int(self.pet_y))

        self.state_timer -= 1
        if self.state_timer <= 0:
            self.decide_next_state(on_window, active_win)

        if self.state == "WALK":
            self.walk_frame += 1
            if self.walk_frame % 4 < 2: 
                self.appearance_changed.emit("walk1")
            else:
                self.appearance_changed.emit("walk2")

    def change_state(self, new_state, duration=0):
        if self.state == new_state and new_state not in ["WALK", "DRAGGED"]:
            self.state_timer = duration
            return
            
        self.state = new_state
        self.state_timer = duration
        
        if new_state == "STAND": self.appearance_changed.emit("stand"); self.vx = 0
        elif new_state == "SIT": self.appearance_changed.emit("sit"); self.vx = 0
        elif new_state == "SITTING": self.appearance_changed.emit("sitting"); self.vx = 0
        
        elif new_state == "STANDING": self.appearance_changed.emit("standing"); self.vx = 0; self.stand_has_acted = False
        
        elif new_state == "SAY_HI1": self.appearance_changed.emit("say_hi1"); self.vx = 0
        elif new_state == "SAY_HI2": self.appearance_changed.emit("say_hi2"); self.vx = 0
        elif new_state == "THINKING": self.appearance_changed.emit("thinking"); self.vx = 0
        elif new_state == "DRAGGED": self.appearance_changed.emit("catching"); self.vx = 0; self.vy = 0
        elif new_state == "FALLING": self.appearance_changed.emit("felling")
        elif new_state == "FELL": self.appearance_changed.emit("fell"); self.vx = 0; self.state_timer = 20
        
        elif new_state == "GETUP": self.appearance_changed.emit("getup"); self.vx = 0; self.state_timer = 48; self.stand_has_acted = False 
        
        elif new_state == "JUMP": self.appearance_changed.emit("jump")
        elif new_state == "SLEEP": self.appearance_changed.emit("sleep"); self.vx = 0 
        elif new_state == "READING": self.appearance_changed.emit("reading"); self.vx = 0 

    def decide_next_state(self, on_window, active_win=None):
        if self.state == "FELL":
            self.change_state("GETUP")
            return
        elif self.state == "GETUP":
            self.change_state("STAND", random.randint(100, 200)) 
            return
            
        elif self.state == "SITTING":
            self.change_state("SIT", random.randint(100, 200))
            return
        elif self.state == "STANDING":
            self.change_state("STAND", random.randint(100, 200)) 
            return
        
        elif self.state in ["FALLING", "DRAGGED", "JUMP"]: 
            return 

        if self.state == "STAND":
            r = random.random()

            if not on_window and active_win:
                if r < 0.50: 
                    safe_left = active_win.left
                    safe_right = max(active_win.left, active_win.right - int(self.pet_width))
                    
                    target_x = float(random.randint(int(safe_left), int(safe_right)))
                    target_y = float(active_win.top - self.pet_height + 25)
                    
                    T = 30.0
                    g = 2.0 
                    
                    self.vx = (target_x - self.pet_x) / T
                    self.vy = (target_y - self.pet_y - 0.5 * g * (T ** 2)) / T
                    
                    self.change_state("JUMP", 9999) 
                    return

            r2 = random.random()
            
            if not self.stand_has_acted:
                if r2 < 0.30:
                    self.change_state("STAND", random.randint(100, 200))
                elif r2 < 0.55:
                    self.stand_has_acted = True 
                    self.change_state("WALK", random.randint(60, 100))
                    self.vx = 3.0 * random.choice([-1, 1]) 
                elif r2 < 0.70 and not on_window:
                    self.stand_has_acted = True 
                    self.change_state("SAY_HI1", 53)
                elif r2 < 0.85:
                    self.stand_has_acted = True 
                    self.change_state("SLEEP", random.randint(100, 200))
                else:
                    self.stand_has_acted = True 
                    self.change_state("READING", 127)
            else:
                if r2 < 0.30:
                    self.change_state("STAND", random.randint(100, 200))
                elif r2 < 0.50:
                    self.change_state("WALK", random.randint(60, 100))
                    self.vx = 3.0 * random.choice([-1, 1]) 
                elif r2 < 0.60 and not on_window:
                    self.change_state("SAY_HI1", 53)
                elif r2 < 0.80:
                    self.sit_has_thought = False
                    self.change_state("SITTING", 45) 
                elif r2 < 0.90:
                    self.change_state("SLEEP", random.randint(100, 200))
                else:
                    self.change_state("READING", 127)
            return

        if self.state in ["WALK", "SAY_HI1", "SLEEP", "READING"]:
            self.change_state("STAND", random.randint(100, 200)) 
            return

        if self.state in ["SIT", "THINKING", "SAY_HI2"]:
            if self.state == "THINKING":
                self.change_state("SAY_HI2", 25) 
                return
                
            if self.state == "SAY_HI2":
                self.change_state("SIT", random.randint(100, 200)) 
                return

            if not self.sit_has_thought:
                if random.random() < 0.5:
                    self.sit_has_thought = True 
                    self.change_state("THINKING", 30) 
                else:
                    self.change_state("SIT", random.randint(100, 200))
            else:
                if random.random() < 0.6: 
                    self.change_state("STANDING", 40) 
                else:
                    self.change_state("SIT", random.randint(100, 200))
            return