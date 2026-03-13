import random
import ctypes
from ctypes.wintypes import RECT
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, QPoint
from PyQt6.QtWidgets import QApplication

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
        
        self.sit_has_thought = False 
        self.stand_has_acted = False 
        self.is_chatting = False
        
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
            self.change_state("STAND", 20)

    # ================= 核心修复：分离所有窗口与可踩踏窗口 =================
    def get_all_visible_windows(self, screen_geo, ratio):
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi 
        
        hwnd = user32.GetTopWindow(None)
        windows_info = []
        
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        DWMWA_CLOAKED = 14
        
        while hwnd:
            if hwnd != self.win_id and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                
                cloaked = ctypes.wintypes.DWORD()
                res = dwmapi.DwmGetWindowAttribute(
                    hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
                )
                if res == 0 and cloaked.value != 0:
                    hwnd = user32.GetWindow(hwnd, 2)
                    continue 

                class_name = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_name, 256)
                c_name = class_name.value
                
                if c_name not in ["WorkerW", "Progman", "Shell_TrayWnd", "Windows.UI.Core.CoreWindow"]:
                    rect = RECT()
                    res = dwmapi.DwmGetWindowAttribute(
                        hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
                    )
                    if res != 0: 
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    
                    rect.left = int(rect.left / ratio)
                    rect.right = int(rect.right / ratio)
                    rect.top = int(rect.top / ratio)
                    rect.bottom = int(rect.bottom / ratio)
                    
                    width = rect.right - rect.left
                    height = rect.bottom - rect.top
                    
                    if width > 0 and height > 0:
                        # 判断是否为全屏/最大化窗口（它们不能作为地板，但必须作为遮挡物）
                        is_fullscreen = (width >= screen_geo.width() - 20) and (height >= screen_geo.height() - 20)
                        # 判断是否是可以踩踏的有效小窗口
                        is_valid_floor = not is_fullscreen and width > 100 and height > 50
                        
                        windows_info.append({
                            "rect": rect,
                            "is_valid_floor": is_valid_floor
                        })
                        
            hwnd = user32.GetWindow(hwnd, 2) 
            
        return windows_info
    # ======================================================================

    def game_loop(self):
        if self.state == "DRAGGED": 
            return 
            
        if self.is_chatting:
            self.position_changed.emit(int(self.pet_x), int(self.pet_y))
            return
            
        self.pet_x += self.vx
        self.pet_y += self.vy
        
        pet_point = QPoint(int(self.pet_x + self.pet_width / 2), int(self.pet_y + self.pet_height / 2))
        current_screen = QApplication.screenAt(pet_point)
        
        if current_screen:
            ratio = current_screen.devicePixelRatio()
            screen_geo = current_screen.availableGeometry()
        else:
            ratio = 1.0
            screen_geo = self.screen_rect
            
        screen_floor_y = screen_geo.bottom() - self.pet_height

        # 获取带有地板属性标记的窗口列表
        all_windows_info = self.get_all_visible_windows(screen_geo, ratio)
        
        highest_floor_y = screen_floor_y
        on_window = False
        pet_center_x = self.pet_x + self.pet_width / 2
        
        if self.state != "DRAGGED":
            for i, win_data in enumerate(all_windows_info):
                # 只有非全屏的有效窗口，才有资格做地板
                if not win_data["is_valid_floor"]:
                    continue
                    
                rect = win_data["rect"]
                if rect.left <= pet_center_x <= rect.right:
                    is_occluded = False
                    # 遍历上方所有窗口（包含全屏大窗口）检测遮挡
                    for j in range(i):
                        hw = all_windows_info[j]["rect"]
                        if hw.left <= pet_center_x <= hw.right and hw.top <= rect.top <= hw.bottom:
                            is_occluded = True
                            break
                    
                    if not is_occluded:
                        window_top_y = rect.top - self.pet_height + 25 
                        
                        if self.vy >= 0: 
                            if self.pet_y <= window_top_y + 80: 
                                if window_top_y < highest_floor_y:
                                    highest_floor_y = window_top_y
                                    on_window = True
                        else: 
                            if self.pet_y <= window_top_y:
                                if window_top_y < highest_floor_y:
                                    highest_floor_y = window_top_y
                                    on_window = True

        target_floor_y = highest_floor_y

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

        if self.pet_x < screen_geo.left(): 
            self.pet_x = screen_geo.left()
            self.vx = abs(self.vx)  
        elif self.pet_x > screen_geo.right() - self.pet_width: 
            self.pet_x = screen_geo.right() - self.pet_width
            self.vx = -abs(self.vx) 

        new_flipped = self.is_flipped
        if self.vx > 0:
            new_flipped = True   
        elif self.vx < 0:
            new_flipped = False  
        else:
            screen_center = screen_geo.left() + screen_geo.width() / 2
            pet_center = self.pet_x + self.pet_width / 2
            new_flipped = (pet_center < screen_center)
            
        if new_flipped != self.is_flipped:
            self.is_flipped = new_flipped
            self.direction_changed.emit(self.is_flipped)

        self.position_changed.emit(int(self.pet_x), int(self.pet_y))

        self.state_timer -= 1
        if self.state_timer <= 0:
            self.decide_next_state(on_window, all_windows_info, screen_geo)

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
        elif new_state == "STAND_READING": self.appearance_changed.emit("stand_reading"); self.vx = 0 
        elif new_state == "SIT_READING": self.appearance_changed.emit("sit_reading"); self.vx = 0

    def decide_next_state(self, on_window, all_windows_info, screen_geo):
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

            if not on_window and all_windows_info:
                if r < 0.50: 
                    valid_targets = []
                    for i, win_data in enumerate(all_windows_info):
                        if not win_data["is_valid_floor"]:
                            continue
                            
                        tw = win_data["rect"]
                        center_x = (tw.left + tw.right) / 2
                        is_occluded = False
                        
                        # 同样在决定跳跃目标时，做严格的遮挡剔除
                        for j in range(i):
                            hw = all_windows_info[j]["rect"]
                            if hw.left <= center_x <= hw.right and hw.top <= tw.top <= hw.bottom:
                                is_occluded = True
                                break
                                
                        if not is_occluded:
                            valid_targets.append(tw)

                    if valid_targets:
                        target_win = random.choice(valid_targets)
                        safe_left = target_win.left
                        safe_right = max(target_win.left, target_win.right - int(self.pet_width))
                        
                        if safe_right > safe_left: 
                            target_x = float(random.randint(safe_left, safe_right))
                            target_y = float(target_win.top - self.pet_height + 25)
                            
                            T = 30.0
                            g = 2.0 
                            
                            self.vx = (target_x - self.pet_x) / T
                            self.vy = (target_y - self.pet_y - 0.5 * g * (T ** 2)) / T
                            
                            self.change_state("JUMP", 9999) 
                            return

            # ================= 新增逻辑：在窗口上时有概率主动跳下来 =================
            elif on_window:
                if r < 0.20: # 20% 的概率待腻了想跳下去
                    safe_left = screen_geo.left() + 50
                    safe_right = screen_geo.right() - int(self.pet_width) - 50
                    
                    if safe_right > safe_left:
                        target_x = float(random.randint(safe_left, safe_right))
                        target_y = float(screen_geo.bottom() - self.pet_height) 
                        
                        T = 35.0 
                        g = 2.0 
                        
                        self.vx = (target_x - self.pet_x) / T
                        self.vy = (target_y - self.pet_y - 0.5 * g * (T ** 2)) / T
                        
                        self.change_state("JUMP", 9999) 
                        return
            # ====================================================================

            r2 = random.random()
            
            if not self.stand_has_acted:
                if r2 < 0.40:
                    self.change_state("STAND", random.randint(100, 200))
                elif r2 < 0.65:
                    self.stand_has_acted = True 
                    self.change_state("WALK", random.randint(60, 100))
                    self.vx = 3.0 * random.choice([-1, 1]) 
                elif r2 < 0.75 and not on_window:
                    self.stand_has_acted = True 
                    self.change_state("SAY_HI1", 53)
                elif r2 < 0.85:
                    self.stand_has_acted = True 
                    self.change_state("STAND_READING", 125) 
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
                elif r2 < 0.75:
                    self.change_state("STAND_READING", 125)
                elif r2 < 0.90:
                    self.sit_has_thought = False
                    self.change_state("SITTING", 45) 
                else:
                    self.change_state("SLEEP", random.randint(100, 200))
            return

        if self.state in ["WALK", "SAY_HI1", "SLEEP", "STAND_READING"]:
            self.change_state("STAND", random.randint(100, 200)) 
            return

        if self.state in ["SIT", "THINKING", "SAY_HI2", "SIT_READING"]:
            if self.state == "THINKING":
                self.change_state("SAY_HI2", 25) 
                return
                
            if self.state == "SAY_HI2":
                self.change_state("SIT", random.randint(100, 200)) 
                return
                
            if self.state == "SIT_READING":
                self.change_state("SIT", random.randint(100, 200)) 
                return

            if not self.sit_has_thought:
                r3 = random.random()
                if r3 < 0.40:
                    self.sit_has_thought = True 
                    self.change_state("THINKING", 30) 
                elif r3 < 0.70:
                    self.sit_has_thought = True
                    self.change_state("SIT_READING", 135) 
                else:
                    self.change_state("SIT", random.randint(100, 200))
            else:
                r3 = random.random()
                if r3 < 0.40: 
                    self.change_state("STANDING", 40) 
                elif r3 < 0.60:
                    self.change_state("SIT_READING", 135)
                else:
                    self.change_state("SIT", random.randint(100, 200))
            return