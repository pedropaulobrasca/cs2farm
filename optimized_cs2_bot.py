import cv2
import numpy as np
import mss
import time
import torch
import win32api
import win32con
import win32gui
import ctypes
import os
import math
import keyboard
import random
from threading import Thread
from ultralytics import YOLO

class CS2AimBot:
    def __init__(self):
        # Core settings
        self.running = True
        self.bot_active = True
        self.enable_debug = False  # Kapatıldı - arka planda çalışma için
        
        # Model settings
        self.model_path = r"runs\detect\cs2_model2\weights\best.pt"
        self.model = None
        self.model_loaded = False
        self.confidence_threshold = 0.4  # Daha düşük değer daha fazla hedef algılar
        
        self.auto_buy_enabled = True  # Otomatik satın alma etkin
        self.last_buy_time = 0  # Son satın alma zamanı
        self.buy_interval = 3.0  # Satın alma kontrolü aralığı (saniye)
        self.buy_keys = [
            'b',  # Satın alma menüsü
            '4',  # Tüfekler
            '2'   # M4A1-S
        ]

        # Aim settings
        self.auto_fire = True
        self.target_head = False  # Artık kafa+boyun bölgesine nişan al
        self.fire_delay = 0.07  # M4A1-S için ideal atış hızı
        self.last_fire_time = 0
        self.burst_mode = False  # Spray modu kullanılacak, burst kapalı
        self.burst_count = 0  # Aktif burst sayacı
        self.max_burst_shots = 2  # Burst başına daha fazla atış
        self.burst_cooldown = 0.5  # M4A1-S sprayler arası bekleme
        self.last_burst_time = 0  # Son burst zamanı
        
        # FOV settings - daha küçük tarama alanı
        self.fov_width = 640
        self.fov_height = 480
        
        # Mouse control settings - İKİ AYRI HASSASİYET DEĞERİ EKLENDI
        self.aim_sensitivity = 3  # Arttırılmış nişan alma hassasiyeti (daha hızlı aim)
        self.scan_sensitivity = 12.0  # Arttırılmış tarama hassasiyeti (çok daha hızlı dönüş)
        self.mouse_mode = 0  # Y-ters modunda başlat (CS2 için en uygun)
        
        # Rotation settings - DAHA BÜYÜK DÖNÜŞLER
        self.rotation_power = 200  # Daha da YÜKSEK dönüş hızı 
        self.rotation_cooldown = 0.1  # Daha hızlı dönüş aralıkları
        self.last_rotation_time = 0
        
        # Scanning settings - ÇOK DAHA BÜYÜK VE HIZLI ADIMLAR
        self.auto_scan = True
        self.scan_angle = 0
        self.scan_step = 200  # Çok daha BÜYÜK adımlar (30° -> 40°)
        self.scan_speed = 0.05  # Çok daha hızlı tarama (0.1 -> 0.05)
        self.last_scan_time = 0
        self.scanning_mode = 0  # 0: Normal, 1: 360 derece, 2: Zigzag
        
        # 360 Derece Tarama için
        self.full_scan_interval = 4.0  # 4 saniyede bir 360 derece
        self.last_full_scan_time = 0
        self.is_full_scanning = True
        self.full_scan_progress = 0
        
        # Recoil control - M4A1-S spray pattern
        self.recoil_control_enabled = True
        self.recoil_strength = 0.8  # Daha güçlü tepme kontrolü şiddeti (M4A1-S spray için)
        self.shots_fired = 0
        self.max_shots_before_reset = 20  # Daha uzun spray paterni desteği
        self.recoil_reset_time = 0.4  # Tepme sıfırlama süresi - daha uzun
        self.last_recoil_time = 0
        
        # M4A1-S spray pattern değerleri
        self.m4a1s_pattern = [
            (0, 0),      # 1. atış
            (0, 2),      # 2. atış
            (0, 4),      # 3. atış
            (0, 6),      # 4. atış
            (0, 8),      # 5. atış
            (-1, 8),     # 6. atış
            (-1, 8),     # 7. atış
            (1, 6),      # 8. atış
            (1, 6),      # 9. atış
            (1, 4),      # 10. atış
            (2, 4),      # 11. atış
            (2, 3),      # 12. atış
            (-3, 3),     # 13. atış
            (-3, 2),     # 14. atış
            (-2, 2),     # 15. atış
            (-2, 1),     # 16. atış
            (2, 1),      # 17. atış
            (2, 1),      # 18. atış
            (2, 0),      # 19. atış
            (0, 0),      # 20. atış
        ]
        
        # Target settings  
        self.head_offset_y = 15  # Boyun/göğüs bölgesi hedefleme (kafa yerine)
        self.precise_aim_enabled = True  # Hassas nişan alma modunu etkinleştir
        self.precise_aim_steps = 2  # Daha az adımla daha hızlı nişan
        self.spray_mode = True  # M4A1-S spray modu
        
        # Target filtering
        self.filter_waiting_players = True  # 10 saniye bekleyen oyuncuları filtrele
        self.player_states = {}  # Oyuncu durumlarını takip et
        self.waiting_detection_keys = ["waiting", "spawn", "respawn", "dead"]  # Bekleme durumu için anahtar kelimeler
        
        # Screen settings
        self.monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
        self.screen_center_x = None
        self.screen_center_y = None
        
        # Game window
        self.cs2_window = None
        self.cs2_rect = None
        
        # Performance
        self.fps_array = []
        
        # System initialization
        self._init_system()
        
    def _init_system(self):
        """Initialize the system components"""
        print("\n=== CS2 AimBot Initialization ===")
        
        # Load model
        self._load_model()
        
        # Find CS2 window
        self._find_cs2_window()
        
        # Get screen info
        self._get_screen_info()
        
        print("\n=== Initialization Complete ===")
        print("Press F10 to toggle the bot ON/OFF")
        print("Press F9 to toggle debug view")
        print("Press F1 to exit the program")
        
    def _load_model(self):
        """Load the YOLO model"""
        try:
            print("Loading YOLO model...")
            if not os.path.exists(self.model_path):
                print(f"Warning: Model not found at {self.model_path}")
                
                # Try alternate paths
                alt_paths = [
                    "runs/detect/cs2_model/weights/best.pt",
                    "best.pt",
                    "yolov8n.pt"  # Fallback to default
                ]
                
                for path in alt_paths:
                    if os.path.exists(path):
                        print(f"Using alternate model: {path}")
                        self.model_path = path
                        break
            
            # Load model with optimization settings
            self.model = YOLO(self.model_path)
            
            # Use half precision if CUDA available
            if torch.cuda.is_available():
                print("CUDA available - Using GPU acceleration")
                self.model.to('cuda')
                self.model.model.half()  # Use FP16 for better performance
            
            # Set confidence threshold
            self.model.conf = self.confidence_threshold
            
            # Test model with tiny frame
            test_frame = np.zeros((100, 100, 3), dtype=np.uint8)
            _ = self.model(test_frame)
            
            self.model_loaded = True
            print("✅ Model loaded successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def _find_cs2_window(self):
        """Find the CS2 game window"""
        try:
            # Try different window titles
            window_titles = [
                "Counter-Strike 2",
                "Counter-Strike",
                "Counter Strike 2",
                "cs2"
            ]
            
            for title in window_titles:
                hwnd = win32gui.FindWindow(None, title)
                if hwnd != 0:
                    self.cs2_window = hwnd
                    self.cs2_rect = win32gui.GetWindowRect(hwnd)
                    print(f"✅ Found CS2 window: {title}")
                    return True
            
            print("⚠️ CS2 window not found. Using fullscreen mode.")
            return False
            
        except Exception as e:
            print(f"Error finding CS2 window: {e}")
            return False
    
    def _get_screen_info(self):
        """Get screen information"""
        try:
            with mss.mss() as sct:
                # If CS2 window found, use its dimensions
                if self.cs2_rect:
                    left, top, right, bottom = self.cs2_rect
                    
                    # Check if fullscreen
                    window_width = right - left
                    window_height = bottom - top
                    
                    # Get monitor info
                    monitor_info = sct.monitors[1]  # Primary monitor
                    
                    # If similar to monitor size, likely fullscreen
                    if (abs(window_width - monitor_info["width"]) < 20 and 
                        abs(window_height - monitor_info["height"]) < 20):
                        print("Detected fullscreen mode")
                        border_adjust = 0
                        title_adjust = 0
                    else:
                        print("Detected windowed mode")
                        border_adjust = 8  # Window border
                        title_adjust = 31  # Title bar
                    
                    # Update monitor info
                    self.monitor = {
                        "left": left + border_adjust,
                        "top": top + title_adjust,
                        "width": right - left - (border_adjust * 2),
                        "height": bottom - top - title_adjust - border_adjust
                    }
                else:
                    # Use primary monitor
                    self.monitor = sct.monitors[1]
                
                # Calculate screen center
                self.screen_center_x = self.monitor['width'] // 2
                self.screen_center_y = self.monitor['height'] // 2
                
                print(f"Screen center: ({self.screen_center_x}, {self.screen_center_y})")
                return True
                
        except Exception as e:
            print(f"Error getting screen info: {e}")
            self.monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
            self.screen_center_x = 960
            self.screen_center_y = 540
            return False
    
    def capture_game_frame(self):
        """Capture the game screen"""
        try:
            with mss.mss() as sct:
                # FOV area centered on crosshair
                area = {
                    'left': self.monitor['left'] + self.screen_center_x - (self.fov_width // 2),
                    'top': self.monitor['top'] + self.screen_center_y - (self.fov_height // 2),
                    'width': self.fov_width,
                    'height': self.fov_height
                }
                
                # Keep within screen bounds
                area['left'] = max(self.monitor['left'], min(area['left'], 
                                  self.monitor['left'] + self.monitor['width'] - self.fov_width))
                area['top'] = max(self.monitor['top'], min(area['top'], 
                                 self.monitor['top'] + self.monitor['height'] - self.fov_height))
                
                # Capture screen
                screenshot = np.array(sct.grab(area))
                frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
                
                return frame, area
                
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None, None
    
    def detect_players(self, frame):
        """Detect players using YOLO"""
        if not self.model or not self.model_loaded:
            return []
            
        try:
            # Run inference with YOLO
            results = self.model(frame, stream=True)
            
            # Process results
            targets = []
            current_time = time.time()
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    # Get detection info
                    confidence = box.conf[0].item()
                    cls_id = int(box.cls[0].item())
                    
                    # Skip low confidence
                    if confidence < self.confidence_threshold:
                        continue
                    
                    # Get class name
                    if cls_id < len(self.model.names):
                        class_name = self.model.names[cls_id]
                    else:
                        class_name = f"class_{cls_id}"
                    
                    # Get bounding box
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    x, y = int(x1), int(y1)
                    w, h = int(x2 - x1), int(y2 - y1)
                    
                    # Filter invalid detections
                    if w < 15 or h < 15:
                        continue
                    if w > self.fov_width * 0.8 or h > self.fov_height * 0.8:
                        continue
                    
                    # Waiting player detection
                    is_waiting = False
                    if self.filter_waiting_players:
                        # OCR benzeri bir sistem olmadığından, pozisyon ve duruş analizi yapacağız
                        
                        # ID oluştur - basit pozisyon bazlı
                        player_id = f"{int(x1)}-{int(y1)}-{class_name}"
                        
                        # Player state kontrolü
                        if player_id in self.player_states:
                            player_state = self.player_states[player_id]
                            
                            # Durum kontrolü - uzun süre hareketsiz kalan oyuncular
                            if current_time - player_state["first_seen"] > 5.0 and player_state["move_count"] < 3:
                                if "waiting" not in player_state:
                                    player_state["waiting"] = True
                                    player_state["waiting_since"] = current_time
                                elif current_time - player_state["waiting_since"] > 3.0:
                                    # 3 saniyeden fazla bekleyen = bekleme durumunda
                                    is_waiting = True
                            
                            # Pozisyon değişikliği kontrolü
                            last_pos = player_state["last_position"]
                            pos_diff = abs(last_pos[0] - x1) + abs(last_pos[1] - y1)
                            
                            if pos_diff > 10:  # Önemli bir hareket var
                                player_state["move_count"] += 1
                                player_state["last_position"] = (x1, y1)
                                if "waiting" in player_state:
                                    del player_state["waiting"]
                        else:
                            # Yeni oyuncu
                            self.player_states[player_id] = {
                                "first_seen": current_time,
                                "last_position": (x1, y1),
                                "move_count": 0
                            }
                        
                        # Eski kayıtları temizle
                        for pid in list(self.player_states.keys()):
                            if current_time - self.player_states[pid]["first_seen"] > 20:
                                del self.player_states[pid]
                                
                        # Bekleme durumundaki oyuncuları filtrele
                        if is_waiting:
                            continue
                    
                    # Calculate center
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Distance from center of FOV
                    fov_center_x = self.fov_width // 2
                    fov_center_y = self.fov_height // 2
                    
                    distance = math.sqrt((center_x - fov_center_x)**2 + 
                                         (center_y - fov_center_y)**2)
                    
                    # Daha hassas kafa tespiti (yakın ve uzak mesafe optimizasyonlu) 
                    # Kutu boyutuna göre değil, mesafeye göre kafa pozisyonu hesapla
                    if h > 120:  # Yakın düşman
                        head_y = y + int(h * 0.08)  # %8 - Daha yukarıdan kafa hedefi
                    else:  # Uzak düşman
                        head_y = y + int(h * 0.12)  # %12 - Uzakta kafa biraz daha aşağıda görünür
                    
                    # Save target
                    targets.append({
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'center_x': center_x,
                        'center_y': center_y,
                        'head_y': head_y,
                        'distance': distance,
                        'confidence': confidence,
                        'class': cls_id,
                        'name': class_name,
                        'is_waiting': is_waiting
                    })
            
            # Sort by distance (closest first)
            targets.sort(key=lambda t: t['distance'])
            
            return targets
            
        except Exception as e:
            print(f"Error in detection: {e}")
            return []
    
    def send_mouse_input_to_game(self, dx, dy, button=None):
        """Send mouse input directly to the game window"""
        try:
            # Use raw input to avoid interfering with user's mouse
            if button == 'left':
                # Fire - use standard mouse event
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.02)  # Short press
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            else:
                # Mouse movement - use standard mouse event
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
            
            return True
            
        except Exception as e:
            print(f"Error sending mouse input: {e}")
            return False
    
    def aim_at_target(self, target):
        """Aim at the target with M4A1-S spray pattern control"""
        try:
            # FOV center
            fov_center_x = self.fov_width // 2
            fov_center_y = self.fov_height // 2
            
            # Boyun/göğüs bölgesine hedefleme (gövde-kafa arası)
            aim_x = target['center_x']
            
            # Mesafeye göre hedef noktası ayarı
            distance_factor = min(1.0, target['distance'] / 250)
            
            # Kafa ile göğüs arası bir nokta - M4A1-S spray için ideal başlangıç
            neck_position = target['head_y'] + self.head_offset_y + int(distance_factor * 10)
            
            # M4A1-S spray'i yukarı doğru gideceği için, daha aşağıdan başlama
            aim_y = neck_position
            
            # Calculate relative movement
            rel_x = aim_x - fov_center_x
            rel_y = aim_y - fov_center_y
            
            # Apply mouse mode (direction correction)
            if self.mouse_mode == 0:   # Normal
                dx = rel_x
                dy = rel_y
            elif self.mouse_mode == 1: # X-Inverted
                dx = -rel_x
                dy = rel_y
            elif self.mouse_mode == 2: # Y-Inverted (Default for most games)
                dx = rel_x
                dy = -rel_y
            else:                      # XY-Inverted
                dx = -rel_x
                dy = -rel_y
            
                            # M4A1-S SPRAY MODU - GÖVDE-KAFA ARASI HEDEF
            if self.precise_aim_enabled:
                # Tek seferde hedefi yakalayan hareket
                initial_dx = dx
                initial_dy = dy
                
                # Recoil control - M4A1-S pattern için hazırlık
                initial_dx, initial_dy = self.apply_recoil_control(initial_dx, initial_dy)
                
                # Hızlı ve kesin hareketi yap
                self.send_mouse_input_to_game(initial_dx, initial_dy)
                
                # Spray için konum düzeltmesi
                if self.spray_mode:
                    # Gövde-kafa arası hedefleme için son ufak düzeltme
                    fine_x = 0
                    # Hafif bir yukarı doğru ayarlama
                    fine_y = -3 if self.mouse_mode == 0 or self.mouse_mode == 1 else 3
                    self.send_mouse_input_to_game(fine_x, fine_y)
            else:
                # Apply sensitivity - NİŞAN ALMA HASSASİYETİ KULLANILIYOR
                dx = dx * self.aim_sensitivity
                dy = dy * self.aim_sensitivity
                
                # Recoil control
                dx, dy = self.apply_recoil_control(dx, dy)
                
                # Limit movement
                max_move = 50
                dx = max(-max_move, min(dx, max_move))
                dy = max(-max_move, min(dy, max_move))
                
                # Move mouse in steps
                steps = 2
                step_dx = dx / steps
                step_dy = dy / steps
                
                for i in range(steps):
                    self.send_mouse_input_to_game(step_dx, step_dy)
                    time.sleep(0.001)  # Very short delay
            
            # Return distance to target
            distance = math.sqrt(rel_x**2 + rel_y**2)
            return distance
            
        except Exception as e:
            print(f"Error aiming: {e}")
            return 1000
    
    def fire(self):
        """M4A1-S spray ile etkili atış"""
        current_time = time.time()
        
        # M4A1-S Spray Modu (uzun burst)
        if self.spray_mode:
            # Burst içindeki atışlar arası gecikme kontrolü
            if current_time - self.last_fire_time < self.fire_delay:
                return False
            
            # Atış sınırı kontrolü
            if self.shots_fired >= self.max_shots_before_reset:
                # Sprayi resetle ve bekleme süresi
                if current_time - self.last_burst_time < self.burst_cooldown:
                    return False
                else:
                    # Yeni spray başlat
                    self.shots_fired = 0
                    self.last_burst_time = current_time
            
            # Atış yap
            self.send_mouse_input_to_game(0, 0, 'left')
            self.last_fire_time = current_time
            self.last_recoil_time = current_time
            
            # Recoil ve spray takibi
            self.shots_fired += 1
            
            # Spray durumunu logla - her 5. atışta
            if self.shots_fired % 5 == 0:
                print(f"M4A1-S Spray: {self.shots_fired}/{self.max_shots_before_reset} atış")
            
            return True
        
        # Orijinal burst veya normal atış modu (yedek olarak duruyor)
        else:
            # Burst kontrolü
            if self.burst_mode:
                # Burst içinde mi?
                if self.burst_count > 0:
                    # Burst içindeki atışlar arası gecikme kontrolü
                    if current_time - self.last_fire_time < self.fire_delay:
                        return False
                    
                    # Atış yap
                    self.send_mouse_input_to_game(0, 0, 'left')
                    self.last_fire_time = current_time
                    self.last_recoil_time = current_time
                    
                    # Recoil takibi
                    self.shots_fired += 1
                    if self.shots_fired > self.max_shots_before_reset:
                        self.shots_fired = self.max_shots_before_reset
                    
                    # Burst sayacını güncelle
                    self.burst_count -= 1
                    
                    return True
                else:
                    # Burst arası bekleme
                    if current_time - self.last_burst_time < self.burst_cooldown:
                        return False
                    
                    # Yeni burst başlat
                    self.burst_count = self.max_burst_shots
                    self.last_burst_time = current_time
                    
                    # İlk atışı yap
                    self.send_mouse_input_to_game(0, 0, 'left')
                    self.last_fire_time = current_time
                    self.last_recoil_time = current_time
                    
                    # Recoil takibi
                    self.shots_fired += 1
                    
                    # Burst sayacını güncelle
                    self.burst_count -= 1
                    
                    return True
            else:
                # Normal atış modu
                if current_time - self.last_fire_time < self.fire_delay:
                    return False
                    
                # Atış yap
                self.send_mouse_input_to_game(0, 0, 'left')
                self.last_fire_time = current_time
                self.last_recoil_time = current_time
                
                # Recoil takibi
                self.shots_fired += 1
                if self.shots_fired > self.max_shots_before_reset:
                    self.shots_fired = self.max_shots_before_reset
                    
                return True
    
    def scan_for_targets(self):
        """Enhanced scanning with different modes and 360-degree capability"""
        current_time = time.time()
        
        # Check for full 360 scan interval
        if current_time - self.last_full_scan_time > self.full_scan_interval and not self.is_full_scanning:
            print("Başlatılıyor: 360 derece tam tarama")
            self.is_full_scanning = True
            self.full_scan_progress = 0
            self.last_full_scan_time = current_time
        
                    # If in full scan mode, rotate 360 degrees
        if self.is_full_scanning:
            if current_time - self.last_rotation_time < self.rotation_cooldown * 0.3:  # Çok daha hızlı döndür
                return
                
            # Daha büyük bir dönüş adımı - 360 dereceyi 8 adımda tamamla (daha hızlı)
            rotation_amount = self.rotation_power * 1.2  # Çok daha büyük dönüş
            self.send_mouse_input_to_game(rotation_amount, 0)
            
            self.full_scan_progress += 1
            self.last_rotation_time = current_time
            
            # 8 adımda 360 dereceyi tamamla (daha hızlı)
            if self.full_scan_progress >= 12:
                self.is_full_scanning = False
                print("Tamamlandı: 360 derece tam tarama")
            
            return
        
        # Normal tarama modu
        if current_time - self.last_scan_time < self.scan_speed:
            return
            
        # Only scan if enough time passed since last rotation
        if current_time - self.last_rotation_time < self.rotation_cooldown:
            return
            
        # Initialize scan direction if needed
        if not hasattr(self, 'scan_direction'):
            self.scan_direction = 1  # 1 for right, -1 for left
            self.vertical_adjustment_counter = 0
        
        # Move mouse horizontally for scanning - TARAMA HASSASİYETİ KULLANILIYOR
        rotation_amount = self.rotation_power * self.scan_direction
        # Daha büyük hareket - düşmanları hızlı taramak için 
        self.send_mouse_input_to_game(rotation_amount, 0)
        
        # Track scan angle
        self.scan_angle = (self.scan_angle + (self.scan_step * self.scan_direction)) % 360
        
        self.last_scan_time = current_time
        self.last_rotation_time = current_time
    
    def apply_recoil_control(self, dx, dy):
        """Apply M4A1-S spray pattern recoil control"""
        if not self.recoil_control_enabled:
            return dx, dy
        
        current_time = time.time()
        
        # Reset recoil after some time without firing
        if current_time - self.last_recoil_time > self.recoil_reset_time:
            self.shots_fired = 0
        
        # M4A1-S spray pattern compensation
        if self.shots_fired > 0 and self.shots_fired <= len(self.m4a1s_pattern):
            # Get pattern compensation for current shot
            pattern_idx = min(self.shots_fired - 1, len(self.m4a1s_pattern) - 1)
            pattern_x, pattern_y = self.m4a1s_pattern[pattern_idx]
            
            # Paterni uygula - Y eksenini ters çevir
            if self.mouse_mode == 0 or self.mouse_mode == 1:  # Normal veya X-ters
                dx -= pattern_x * self.recoil_strength
                dy -= pattern_y * self.recoil_strength
            else:  # Y-ters veya XY-ters 
                dx -= pattern_x * self.recoil_strength
                dy += pattern_y * self.recoil_strength
            
            # Debug mesajı
            if self.enable_debug and self.shots_fired % 5 == 0:
                print(f"M4A1-S spray kontrolü: Atış #{self.shots_fired}, Düzeltme: ({pattern_x}, {pattern_y})")
        
        return dx, dy
    
    def draw_debug_info(self, frame, targets, fps):
        """Draw debug information on frame"""
        if not self.enable_debug:
            return None
            
        debug_frame = frame.copy()
        
        # Draw status info
        cv2.putText(debug_frame, f"FPS: {fps:.1f}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        status_text = "BOT: ON" if self.bot_active else "BOT: OFF"
        cv2.putText(debug_frame, status_text, (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Draw targets
        for i, target in enumerate(targets):
            # Bounding box
            color = (0, 255, 0) if i == 0 else (255, 0, 0)
            cv2.rectangle(debug_frame, (target['x'], target['y']), 
                         (target['x'] + target['width'], target['y'] + target['height']), 
                         color, 2)
            
            # Confidence
            label = f"{target['name']} ({target['confidence']:.2f})"
            cv2.putText(debug_frame, label, (target['x'], target['y'] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Head target
            if self.target_head and i == 0:
                head_y = target['head_y'] + self.head_offset_y
                cv2.circle(debug_frame, (target['center_x'], head_y), 5, (0, 0, 255), -1)
        
        # Draw crosshair
        center_x, center_y = self.fov_width // 2, self.fov_height // 2
        cv2.line(debug_frame, (center_x - 10, center_y), (center_x + 10, center_y), (255, 255, 255), 2)
        cv2.line(debug_frame, (center_x, center_y - 10), (center_x, center_y + 10), (255, 255, 255), 2)
        
        return debug_frame
    
    def handle_keys(self):
        """Handle keyboard controls"""
        # Exit
        if keyboard.is_pressed('f1'):
            self.running = False
            print("Exiting...")
            return True
        
        # Toggle bot
        if keyboard.is_pressed('f10'):
            self.bot_active = not self.bot_active
            status = "ENABLED" if self.bot_active else "DISABLED"
            print(f"Bot {status}")
            time.sleep(0.3)  # Prevent multiple toggles
        
        # Toggle debug view
        if keyboard.is_pressed('f9'):
            self.enable_debug = not self.enable_debug
            status = "ENABLED" if self.enable_debug else "DISABLED"
            print(f"Debug view {status}")
            time.sleep(0.3)
        
        # Toggle head targeting
        if keyboard.is_pressed('h'):
            self.target_head = not self.target_head
            target_type = "HEAD" if self.target_head else "CENTER"
            print(f"Target mode: {target_type}")
            time.sleep(0.3)
            
        # Toggle precise aim mode
        if keyboard.is_pressed('p'):
            self.precise_aim_enabled = not self.precise_aim_enabled
            status = "ENABLED" if self.precise_aim_enabled else "DISABLED"
            print(f"Precise aim {status}")
            time.sleep(0.3)
            
        # Toggle burst mode
        if keyboard.is_pressed('b'):
            self.burst_mode = not self.burst_mode
            status = "ENABLED" if self.burst_mode else "DISABLED"
            print(f"Burst mode {status}")
            time.sleep(0.3)
            
        # Toggle recoil control
        if keyboard.is_pressed('r'):
            self.recoil_control_enabled = not self.recoil_control_enabled
            status = "ENABLED" if self.recoil_control_enabled else "DISABLED"
            print(f"Recoil control {status}")
            time.sleep(0.3)
            
        # Toggle filter waiting players
        if keyboard.is_pressed('w'):
            self.filter_waiting_players = not self.filter_waiting_players
            status = "ENABLED" if self.filter_waiting_players else "DISABLED"
            print(f"Filter waiting players {status}")
            time.sleep(0.3)
            
        # Trigger 360 scan
        if keyboard.is_pressed('t'):
            if not self.is_full_scanning:
                print("Başlatılıyor: 360 derece tam tarama")
                self.is_full_scanning = True
                self.full_scan_progress = 0
                self.last_full_scan_time = time.time()
            time.sleep(0.3)
        
        # Adjust AIM sensitivity (not scan)
        if keyboard.is_pressed('f5'):
            self.aim_sensitivity = max(0.1, self.aim_sensitivity - 0.1)
            print(f"Aim sensitivity: {self.aim_sensitivity:.1f}")
            time.sleep(0.2)
        
        if keyboard.is_pressed('f6'):
            self.aim_sensitivity = min(5.0, self.aim_sensitivity + 0.1)
            print(f"Aim sensitivity: {self.aim_sensitivity:.1f}")
            time.sleep(0.2)
            
        # Adjust SCAN sensitivity with different keys
        if keyboard.is_pressed('f3'):
            self.scan_sensitivity = max(1.0, self.scan_sensitivity - 0.5)
            self.rotation_power = int(20 * self.scan_sensitivity)  # Dönüş gücünü de güncelle
            print(f"Scan sensitivity: {self.scan_sensitivity:.1f}, Rotation power: {self.rotation_power}")
            time.sleep(0.2)
        
        if keyboard.is_pressed('f4'):
            self.scan_sensitivity = min(10.0, self.scan_sensitivity + 0.5)
            self.rotation_power = int(20 * self.scan_sensitivity)  # Dönüş gücünü de güncelle
            print(f"Scan sensitivity: {self.scan_sensitivity:.1f}, Rotation power: {self.rotation_power}")
            time.sleep(0.2)
        
        # Adjust mouse mode
        if keyboard.is_pressed('f7'):
            self.mouse_mode = (self.mouse_mode + 1) % 4
            mode_names = ["Normal", "X-Inverted", "Y-Inverted", "XY-Inverted"]
            print(f"Mouse mode: {mode_names[self.mouse_mode]}")
            time.sleep(0.3)
        
        # Toggle auto fire
        if keyboard.is_pressed('f8'):
            self.auto_fire = not self.auto_fire
            status = "ENABLED" if self.auto_fire else "DISABLED"
            print(f"Auto fire {status}")
            time.sleep(0.3)
        
        # Adjust head target height
        if keyboard.is_pressed('up'):
            self.head_offset_y -= 2
            print(f"Head offset: {self.head_offset_y}")
            time.sleep(0.1)
        
        if keyboard.is_pressed('down'):
            self.head_offset_y += 2
            print(f"Head offset: {self.head_offset_y}")
            time.sleep(0.1)
        
        return False
    
    def run(self):
        """Main bot loop"""
        print("\n=== CS2 AimBot Running ===")
        print("Controls:")
        print("F10: Toggle bot ON/OFF")
        print("F9: Toggle debug view")
        print("F8: Toggle auto fire")
        print("F7: Change mouse mode")
        print("F5/F6: Decrease/Increase AIM sensitivity")
        print("F3/F4: Decrease/Increase SCAN sensitivity")
        print("P: Toggle precise aim mode")
        print("B: Toggle burst fire mode")
        print("R: Toggle recoil control")
        print("W: Toggle waiting player filter")
        print("T: Trigger 360 degree scan")
        print("H: Toggle head targeting")
        print("Up/Down: Adjust head target height")
        print("F1: Exit")
        print("==========================\n")
        
        # Variables for targeting
        targeting_active = False
        target_lost_time = 0
        target_lost_timeout = 0.3
        
        # Performance tracking
        last_fps_update = time.time()
        frames_processed = 0
        
        try:
            while self.running:
                # Track performance
                start_time = time.time()
                frames_processed += 1
                
                # Handle keyboard input
                if self.handle_keys():
                    break
                
                # Skip processing if bot is inactive
                if not self.bot_active:
                    time.sleep(0.1)
                    continue
                
                # Capture screen
                frame, scan_area = self.capture_game_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # Detect players
                targets = self.detect_players(frame)
                
                # Update targeting state
                current_time = time.time()
                
                if targets:
                    # Target found
                    target_lost_time = 0
                    
                    was_scanning = not targeting_active
                    targeting_active = True
                    
                    # Aim at closest target
                    closest_target = targets[0]
                    
                    # Small delay when transitioning from scanning to targeting
                    if was_scanning:
                        time.sleep(0.03)
                    
                    # Aim at target
                    distance = self.aim_at_target(closest_target)
                    
                    # M4A1-S spray ile ateş et - tüm mesafelerde etkili
                    if self.auto_fire:
                        # M4A1-S spray - mesafeden bağımsız spray et
                        self.fire()
                else:
                    # No targets
                    if targeting_active:
                        # Lost target - wait before resuming scan
                        if target_lost_time == 0:
                            target_lost_time = current_time
                        
                        # Resume scanning after timeout
                        if current_time - target_lost_time > target_lost_timeout:
                            targeting_active = False
                            target_lost_time = 0
                    
                    # Scan for targets
                    if not targeting_active and target_lost_time == 0 and self.auto_scan:
                        self.scan_for_targets()
                
                # Calculate FPS
                if current_time - last_fps_update >= 1.0:
                    fps = frames_processed / (current_time - last_fps_update)
                    self.fps_array.append(fps)
                    if len(self.fps_array) > 30:
                        self.fps_array.pop(0)
                    
                    avg_fps = sum(self.fps_array) / len(self.fps_array)
                    if frames_processed > 10:  # Only log if significant number of frames
                        sniper_status = "KESKİN NİŞANCI MODU AKTİF" if self.precise_aim_enabled else "Normal nişan modu"
                        print(f"Performance: {avg_fps:.1f} FPS - {sniper_status}")
                    
                    frames_processed = 0
                    last_fps_update = current_time
                
                # Debug display
                if self.enable_debug:
                    debug_frame = self.draw_debug_info(frame, targets, 
                                                      sum(self.fps_array) / len(self.fps_array) if self.fps_array else 0)
                    if debug_frame is not None:
                        cv2.imshow("CS2 AimBot", debug_frame)
                        cv2.waitKey(1)
                
                # Frame rate limiter - aim for 60 FPS max to reduce CPU usage
                elapsed = time.time() - start_time
                sleep_time = max(0, 1/60 - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.enable_debug:
                cv2.destroyAllWindows()
            print("Bot stopped")

if __name__ == "__main__":
    try:
        # Check and install required packages
        required_packages = ["numpy", "opencv-python", "mss", "keyboard", "ultralytics"]
        try:
            import pip
            for package in required_packages:
                try:
                    __import__(package.replace("-", "_").split("=")[0])
                except ImportError:
                    print(f"Installing {package}...")
                    os.system(f"pip install {package}")
        except Exception as e:
            print(f"Package installation warning: {e}")
        
        # Create and start bot
        bot = CS2AimBot()
        bot.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        print("Press Enter to exit...")
        input() 