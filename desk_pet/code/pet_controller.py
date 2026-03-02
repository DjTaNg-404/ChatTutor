# desk_pet/code/pet_controller.py
import random
import ctypes
import sys
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    from ctypes.wintypes import RECT
else:
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

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
        self.stand_has_acted = False # 站立时是否做过动作 (walk, sleep, say_hi1)
        # ==============================================
        
        # ================= 聊天冻结标记 =================
        self.is_chatting = False
        # ==============================================

        self.last_active_win_rect = None  
        
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
        if not IS_WINDOWS or not hasattr(ctypes, "windll"):
            self.last_active_win_rect = None
            return None

        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()

            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            c_name = class_name.value

            if hwnd == 0 or hwnd == user32.GetDesktopWindow() or c_name in ["WorkerW", "Progman", "Shell_TrayWnd"]:
                self.last_active_win_rect = None
                return None

            if hwnd == self.win_id:
                return self.last_active_win_rect

            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            if (rect.right - rect.left) >= self.screen_rect.width() - 20 and (rect.bottom - rect.top) >= self.screen_rect.height() - 20:
                self.last_active_win_rect = None
                return None

            self.last_active_win_rect = rect
            return rect
        except Exception:
            self.last_active_win_rect = None
            return None

    def game_loop(self):
        if self.state == "DRAGGED": 
            return 
            
        # ================= 核心冻结逻辑 =================
        if self.is_chatting:
            # 聊天时无视重力、无视碰撞，仅仅更新坐标即可
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
                window_top_y = active_win.top - self.pet_height + 30 
                
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
        
        # 【修改】：当触发站起时，重置 stand_has_acted 锁，意味着下一轮站立必须重新做动作
        elif new_state == "STANDING": self.appearance_changed.emit("standing"); self.vx = 0; self.stand_has_acted = False
        
        elif new_state == "SAY_HI1": self.appearance_changed.emit("say_hi1"); self.vx = 0
        elif new_state == "SAY_HI2": self.appearance_changed.emit("say_hi2"); self.vx = 0
        elif new_state == "THINKING": self.appearance_changed.emit("thinking"); self.vx = 0
        elif new_state == "DRAGGED": self.appearance_changed.emit("catching"); self.vx = 0; self.vy = 0
        elif new_state == "FALLING": self.appearance_changed.emit("felling")
        elif new_state == "FELL": self.appearance_changed.emit("fell"); self.vx = 0; self.state_timer = 20
        
        # 【修改】：爬起来后也视为新一轮站立，重置锁
        elif new_state == "GETUP": self.appearance_changed.emit("getup"); self.vx = 0; self.state_timer = 48; self.stand_has_acted = False 
        
        elif new_state == "JUMP": self.appearance_changed.emit("jump")
        elif new_state == "SLEEP": self.appearance_changed.emit("sleep"); self.vx = 0 

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

        # ================= 状态发起：当前是 STAND 状态 =================
        if self.state == "STAND":
            r = random.random()

            if not on_window and active_win:
                if r < 0.50: 
                    safe_left = active_win.left
                    safe_right = max(active_win.left, active_win.right - int(self.pet_width))
                    
                    target_x = float(random.randint(safe_left, safe_right))
                    target_y = float(active_win.top - self.pet_height + 30)
                    
                    T = 30.0
                    g = 2.0 
                    
                    self.vx = (target_x - self.pet_x) / T
                    self.vy = (target_y - self.pet_y - 0.5 * g * (T ** 2)) / T
                    
                    self.change_state("JUMP", 9999) 
                    return

            r2 = random.random()
            
            # ================= 强制站立动作锁 =================
            if not self.stand_has_acted:
                if r2 < 0.40:
                    self.change_state("STAND", random.randint(100, 200))
                elif r2 < 0.70:
                    self.stand_has_acted = True 
                    self.change_state("WALK", random.randint(60, 100))
                    self.vx = 3.0 * random.choice([-1, 1]) 
                elif r2 < 0.85 and not on_window:
                    self.stand_has_acted = True 
                    self.change_state("SAY_HI1", 53)
                else:
                    self.stand_has_acted = True 
                    self.change_state("SLEEP", random.randint(100, 200))
            else:
                if r2 < 0.35:
                    self.change_state("STAND", random.randint(100, 200))
                elif r2 < 0.55:
                    self.change_state("WALK", random.randint(60, 100))
                    self.vx = 3.0 * random.choice([-1, 1]) 
                elif r2 < 0.65 and not on_window:
                    self.change_state("SAY_HI1", 53)
                elif r2 < 0.90:
                    self.sit_has_thought = False
                    self.change_state("SITTING", 45) 
                else:
                    self.change_state("SLEEP", random.randint(100, 200))
            return

        # ================= 状态结束：强制回到 STAND 状态 =================
        if self.state in ["WALK", "SAY_HI1", "SLEEP"]:
            self.change_state("STAND", random.randint(100, 200)) 
            return

        # ================= SIT 及衍生动作 =================
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
                    self.change_state("STANDING", 45) 
                else:
                    self.change_state("SIT", random.randint(100, 200))
            return