import cv2
import numpy as np
import time
import torch
import math
import win32api, win32con
import win32gui
import ctypes
from ctypes import windll, Structure, c_long, byref
import pyautogui
from ultralytics import YOLO
import mss
import keyboard

# Windows için DirectInput benzeri düşük seviyeli fare kontrolü
class POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]

class InputEmulator:
    @staticmethod
    def get_cursor_position():
        pt = POINT()
        windll.user32.GetCursorPos(byref(pt))
        return { "x": pt.x, "y": pt.y }
    
    @staticmethod
    def get_cs2_window():
        try:
            hwnd = win32gui.FindWindow(None, "Counter-Strike 2")
            if hwnd == 0:
                hwnd = win32gui.FindWindow(None, "Counter-Strike")
            return hwnd
        except:
            return 0
    
    @staticmethod
    def send_mouse_input_to_game(dx, dy, button=None):
        """Oyuna doğrudan fare girdisi gönder, normal fare kontrolünü etkileme"""
        # Extra mouse_event flag: 0x0001 = MOUSEEVENTF_ABSOLUTE
        # Kullanıcının imlecini hareket ettirmez, sadece oyun içi girdiler gönderir
        
        try:
            # CS2 penceresini bul
            hwnd = InputEmulator.get_cs2_window()
            if hwnd == 0:
                print("CS2 penceresi bulunamadı!")
                return False
            
            # Absolute koordinatlar için ekran boyutunu al
            user32 = ctypes.windll.user32
            user32.SendMessageW(hwnd, win32con.WM_MOUSEMOVE, 0, win32api.MAKELONG(int(dx), int(dy)))
            
            # Fare tuşu girdisi gönder
            if button == "left":
                # Fare sol tuşu bas ve bırak
                user32.SendMessageW(hwnd, win32con.WM_LBUTTONDOWN, 0, 0)
                time.sleep(0.05)
                user32.SendMessageW(hwnd, win32con.WM_LBUTTONUP, 0, 0)
            
            return True
        except Exception as e:
            print(f"Fare girdisi gönderilemedi: {e}")
            return False

class CS2Aimbot:
    def __init__(self, model_path=r"runs\detect\cs2_model2\weights\best.pt"):
        self.model_path = model_path
        self.model = None
        self.confidence_threshold = 0.25  # Lower for more detections
        self.iou_threshold = 0.45

        # Aiming settings (fine-tuned for high precision)
        self.aim_smoothness = 2.0       # At least 2.0 to avoid division by zero
        self.aim_speed = 0.8            # Lower speed to prevent whipping around
        self.headshot_offset = -10      # Adjusted for better headshots
        self.target_lock_threshold = 15  # More lenient threshold
        self.aim_delay = 0.001          # Almost no delay
        
        # Shooting control
        self.auto_shoot = True          # Otomatik ateş etmeyi etkinleştir
        self.shoot_delay = 0.1          # Atışlar arasındaki gecikme

        # Enhanced recoil control patterns
        self.recoil_patterns = {
            "ak47": np.array([
                [0, -2], [0, -2], [0, -3], [-1, -3], [-1, -4], 
                [2, -4], [2, -3], [1, -4], [1, -5], [0, -4],
                [-1, -3], [-2, -4], [-2, -3], [-1, -2], [0, -2], 
                [2, -2], [2, -3], [1, -3], [0, -2], [-1, -2]
            ]),
            "m4a4": np.array([
                [0, -2], [0, -2], [0, -2], [-1, -2], [-1, -3], 
                [1, -3], [1, -2], [1, -3], [0, -3], [0, -2],
                [-1, -2], [-1, -3], [-1, -2], [0, -2], [1, -2], 
                [1, -2], [0, -2], [0, -2], [0, -2], [0, -2]
            ])
        }
        self.current_weapon = "ak47"    # Default weapon pattern
        self.shots_fired = 0
        self.last_shot_time = 0
        self.recoil_control_active = True
        self.recoil_recovery_time = 0.5  # Time after which recoil pattern resets

        # Burst fire settings
        self.burst_fire_enabled = True
        self.burst_size = 4         # Shots per burst
        self.burst_delay = 0.25     # Seconds between bursts
        self.tap_fire_distance = 0.65  # Distance threshold for tap firing (0.0-1.0, percentage of screen)
        
        # Target selection enhancements
        self.priority_zones = {
            "head": 1.0,            # Head priority multiplier
            "upper_body": 0.8,      # Upper body priority multiplier
            "center_screen": 0.7,   # Center of screen priority factor
            "distance": 0.5,        # Distance factor (closer targets prioritized)
            "movement": 0.3         # Moving target priority reduction
        }
        
        # Target tracking settings
        self.target_memory = []     # Remember recent targets for tracking
        self.memory_duration = 0.5  # How long to remember targets (seconds)
        self.movement_prediction = True  # Enable movement prediction for moving targets
        self.prediction_factor = 0.2     # How much to predict movement (0.0-1.0)
        
        # Performance optimizations
        self.using_tensorrt = False  # TensorRT optimization status
        
        # Initialize model with optimizations
        self.load_model()
        
    def load_model(self):
        """Load YOLOv8 model with optimizations for real-time inference"""
        try:
            # Start with standard model
            self.model = YOLO(self.model_path)
            
            # Try to optimize with TensorRT if available
            try:
                import tensorrt
                # Only export once, then load the optimized model
                engine_path = self.model_path.replace('.pt', '_tensorrt.engine')
                if not os.path.exists(engine_path):
                    self.model.export(format='engine', imgsz=640, half=True)
                self.model = YOLO(engine_path)
                self.using_tensorrt = True
                print(f"TensorRT optimization enabled for faster inference")
            except (ImportError, Exception) as e:
                # Fall back to standard PyTorch if TensorRT fails
                print(f"TensorRT optimization not available: {e}")
                # Use half precision for better performance
                self.model.to(torch.device('cuda' if torch.cuda.is_available() else 'cpu'))
                if torch.cuda.is_available():
                    self.model.model.half()  # Use FP16 if GPU available
                    
            print(f"Model loaded successfully: {self.model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None
    
    def preprocess_frame(self, frame):
        """Preprocess frame for optimal detection"""
        # Apply contrast enhancement to make targets more visible
        # Creates a more robust detection in different lighting conditions
        alpha = 1.1  # Contrast control (1.0 means no change)
        beta = 5     # Brightness control (0 means no change)
        
        # Apply brightness/contrast adjustment
        adjusted = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        
        # Convert to RGB for YOLOv8
        if frame.shape[2] == 4:  # BGRA format
            frame_rgb = cv2.cvtColor(adjusted, cv2.COLOR_BGRA2RGB)
        else:  # BGR format
            frame_rgb = cv2.cvtColor(adjusted, cv2.COLOR_BGR2RGB)
            
        return frame_rgb
    
    def detect_targets(self, frame):
        """Detect players in the frame using YOLOv8"""
        if self.model is None:
            return []
            
        # Preprocess the frame
        processed_frame = self.preprocess_frame(frame)
        
        # Run YOLOv8 inference with optimized settings
        results = self.model(
            processed_frame, 
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            max_det=10,  # Limit detections for faster processing
            verbose=False
        )[0]
        
        # Extract and return detection data
        if len(results.boxes) > 0:
            return [{
                "xyxy": box.xyxy[0].cpu().numpy(),  # Convert to numpy array
                "confidence": box.conf[0].item(),
                "class_id": int(box.cls[0].item()),
                "x1y1x2y2": [float(x) for x in box.xyxy[0].tolist()]
            } for box in results.boxes]
        else:
            return []
    
    def select_best_target(self, targets, frame_width, frame_height, frame=None):
        """Select the best target using multiple criteria for optimal accuracy"""
        if not targets:
            return None
            
        # Center of screen coordinates
        center_x, center_y = frame_width // 2, frame_height // 2
        
        # Enhanced scoring system for target selection
        scored_targets = []
        current_time = time.time()
        
        # CS2'de hedef tespitini güçlendir
        print(f"Detected {len(targets)} potential targets")
        
        for i, target in enumerate(targets):
            x1, y1, x2, y2 = target["xyxy"]
            confidence = target["confidence"]
            
            # Debug her hedefi yazdır
            print(f"Target {i}: conf={confidence:.2f}, pos=({int(x1)},{int(y1)})→({int(x2)},{int(y2)})")
            
            # Precise box center calculation
            box_width = x2 - x1
            box_height = y2 - y1
            center_box_x = x1 + (box_width / 2)
            center_box_y = y1 + (box_height / 2)
            
            # Head position estimation (upper 1/5 of the box for CS2 models)
            head_pos_y = y1 + (box_height * 0.18)  # 18% from top, better for CS2
            
            # Distance calculation
            dx_center = center_box_x - center_x
            dy_center = center_box_y - center_y
            distance_center = math.sqrt(dx_center**2 + dy_center**2)
            
            # Distance from crosshair to head
            dx_head = center_box_x - center_x
            dy_head = head_pos_y - center_y
            distance_head = math.sqrt(dx_head**2 + dy_head**2)
            
            # Normalize distances as percentage of screen dimensions
            normalized_dist = distance_center / math.sqrt(frame_width**2 + frame_height**2)
            
            # Size calculation (larger targets are closer and easier to hit)
            box_size = box_width * box_height
            normalized_size = box_size / (frame_width * frame_height)
            
            # CS2: Hedef merkeze ne kadar yakınsa o kadar öncelikli
            center_bonus = 1.0 - (normalized_dist * 2)  # Center proximity bonus
            
            # Movement detection (if tracking is enabled)
            movement_penalty = 0
            if self.target_memory and frame is not None:
                # Check if this target matches any previous ones
                for old_target in self.target_memory:
                    if current_time - old_target["time"] > self.memory_duration:
                        continue  # Skip expired targets
                        
                    old_x1, old_y1, old_x2, old_y2 = old_target["xyxy"]
                    old_center_x = old_x1 + ((old_x2 - old_x1) / 2)
                    old_center_y = old_y1 + ((old_y2 - old_y1) / 2)
                    
                    # Check if it's the same target (by position overlap)
                    if (abs(center_box_x - old_center_x) < box_width * 0.5 and 
                        abs(center_box_y - old_center_y) < box_height * 0.5):
                        
                        # Calculate movement speed
                        movement_x = center_box_x - old_center_x
                        movement_y = center_box_y - old_center_y
                        movement_speed = math.sqrt(movement_x**2 + movement_y**2)
                        
                        # Apply movement penalty to fast-moving targets
                        movement_penalty = movement_speed * self.priority_zones["movement"]
                        break
            
            # Calculate priority score (lower is better) - CS2 için optimize edilmiş
            # Balance multiple factors for optimal target selection
            priority_score = (
                distance_head * 0.4 -                           # Head distance (primary factor)
                normalized_size * 120 +                         # Size bonus (bigger targets better)
                normalized_dist * 80 +                          # Distance penalty
                (1.0 - confidence) * 50 +                       # Lower confidence penalty
                movement_penalty -                              # Moving target penalty
                center_bonus * 50                               # Center of screen bonus
            )
            
            # Store scored target
            scored_targets.append({
                "index": i,
                "target": target,
                "center_x": center_box_x,
                "center_y": center_box_y,
                "head_y": head_pos_y,
                "distance": distance_center,
                "distance_head": distance_head,
                "dx": dx_center,
                "dy": dy_center,
                "dx_head": dx_head,
                "dy_head": dy_head,
                "normalized_dist": normalized_dist,
                "box_size": box_size,
                "priority": priority_score
            })
            
        # Sort targets by priority score (lower is better)
        scored_targets.sort(key=lambda t: t["priority"])
        
        if scored_targets:
            best = scored_targets[0]
            print(f"Best target: {best['index']} with priority {best['priority']:.2f}")
            print(f"Distance from crosshair: {best['distance']:.2f} pixels")
        
        # Update target memory for tracking
        if scored_targets and self.movement_prediction:
            best_target = scored_targets[0]
            self.target_memory.append({
                "xyxy": best_target["target"]["xyxy"],
                "time": current_time
            })
            
            # Remove old targets from memory
            self.target_memory = [t for t in self.target_memory 
                                if current_time - t["time"] <= self.memory_duration]
        
        return scored_targets[0] if scored_targets else None
        
    def calculate_aim_point(self, target, frame_width, frame_height):
        """Calculate precise aim point with headshot adjustment and prediction"""
        # Basic calculations
        center_x = target["center_x"]
        head_y = target["head_y"]
        
        # Apply headshot offset (aim at head)
        adjusted_y = head_y + self.headshot_offset
        
        # Apply movement prediction if enabled
        if self.movement_prediction and len(self.target_memory) >= 2:
            # Get current time for calculations
            current_time = time.time()
            
            # Get the two most recent positions of this target
            recent_positions = sorted(
                [t for t in self.target_memory if current_time - t["time"] <= self.memory_duration],
                key=lambda t: t["time"], 
                reverse=True
            )
            
            if len(recent_positions) >= 2:
                # Calculate movement vector
                current = recent_positions[0]
                previous = recent_positions[1]
                
                # Extract centers
                current_x = current["xyxy"][0] + (current["xyxy"][2] - current["xyxy"][0]) / 2
                current_y = current["xyxy"][1] + (current["xyxy"][3] - current["xyxy"][1]) / 2
                previous_x = previous["xyxy"][0] + (previous["xyxy"][2] - previous["xyxy"][0]) / 2
                previous_y = previous["xyxy"][1] + (previous["xyxy"][3] - previous["xyxy"][1]) / 2
                
                # Calculate velocity
                time_diff = current["time"] - previous["time"]
                if time_diff > 0:
                    velocity_x = (current_x - previous_x) / time_diff
                    velocity_y = (current_y - previous_y) / time_diff
                    
                    # Predict future position (basic linear prediction)
                    prediction_time = 0.1  # 100ms prediction
                    center_x += velocity_x * prediction_time * self.prediction_factor
                    adjusted_y += velocity_y * prediction_time * self.prediction_factor
        
        # Calculate delta from screen center (where the crosshair is)
        delta_x = center_x - (frame_width // 2)
        delta_y = adjusted_y - (frame_height // 2)
        
        return delta_x, delta_y
        
    def mouse_move(self, dx, dy):
        """CS2'ye doğrudan fare hareketi komutu gönder, kullanıcının imlecini etkileme"""
        if self.aim_smoothness <= 1.0:
            # Simple direct movement
            move_x = int(dx * self.aim_speed)
            move_y = int(dy * self.aim_speed)
            InputEmulator.send_mouse_input_to_game(move_x, move_y)
            return
            
        # Human-like adaptive smooth curve movement
        steps = int(self.aim_smoothness)
        # Sıfıra bölme hatasını önle
        if steps <= 1:
            steps = 2  # En az 2 adım olsun
        
        # Bezier curve-like movement - more natural than linear
        # Accelerates, then decelerates for human-like movement pattern
        for i in range(steps):
            # Bezier interpolation factor (accelerate then decelerate)
            t = i / (steps - 1)
            bezier_factor = 4 * t * (1 - t)  # Equivalent to a quadratic bezier curve
            
            # Apply bezier curve to movement (faster in middle, slower at start/end)
            move_factor = bezier_factor * self.aim_speed
            
            # Calculate step size with bezier factor
            step_x = int((dx / steps) * move_factor)
            step_y = int((dy / steps) * move_factor)
            
            # Skip movements that are too small (0 pixels)
            if abs(step_x) < 1 and abs(step_y) < 1:
                continue
                
            # Vary individual step slightly for more human-like movement
            rand_factor = 0.05  # 5% randomness
            rand_x = int(step_x * (1 + (np.random.random() - 0.5) * rand_factor))
            rand_y = int(step_y * (1 + (np.random.random() - 0.5) * rand_factor))
            
            # Apply mouse movement directly to game
            InputEmulator.send_mouse_input_to_game(rand_x, rand_y)
            
            # Adaptive sleep time (slightly randomized for natural movement)
            sleep_time = 0.001 * (1 + (np.random.random() - 0.5) * 0.3)
            time.sleep(sleep_time)
    
    def mouse_click(self):
        """Simulate mouse click with human-like timing and behavior"""
        now = time.time()
        self.shots_fired += 1
        self.last_shot_time = now
        
        # Realistic press and release times
        press_time = 0.02 + (np.random.random() * 0.03)  # 20-50ms press time
        
        # Fire directly into the game
        InputEmulator.send_mouse_input_to_game(0, 0, "left")
    
    def apply_recoil_control(self):
        """Apply recoil compensation based on weapon pattern and shots fired"""
        if not self.recoil_control_active or self.shots_fired == 0:
            return
            
        # Reset recoil counter if we haven't fired for a while
        now = time.time()
        if now - self.last_shot_time > self.recoil_recovery_time:
            self.shots_fired = 0
            return
            
        # Get correct recoil pattern for current weapon
        pattern = self.recoil_patterns.get(self.current_weapon, self.recoil_patterns["ak47"])
        
        # Apply the corresponding recoil compensation if within pattern range
        if self.shots_fired <= len(pattern):
            # Get the recoil vector for current shot
            recoil_x, recoil_y = pattern[self.shots_fired - 1]
            
            # Apply compensation (negative of recoil)
            InputEmulator.send_mouse_input_to_game(recoil_x, recoil_y)
    
    def should_fire(self, target, frame_width, frame_height):
        """Determine if we should fire based on multiple tactical factors"""
        # Never fire if no target
        if not target:
            return False
            
        # Check if aiming is precise enough - daha hoşgörülü
        precise_aim = (abs(target["dx_head"]) < self.target_lock_threshold * 1.5 and 
                      abs(target["dy_head"]) < self.target_lock_threshold * 1.5)
        
        # If burst fire is enabled, apply burst logic
        if self.burst_fire_enabled:
            now = time.time()
            
            # Check if target is far away (use normalized distance)
            is_distant_target = target["normalized_dist"] > self.tap_fire_distance
            
            if is_distant_target:
                # For distant targets, use tap firing (more accurate)
                if now - self.last_shot_time < 0.25:  # Daha hızlı (was 0.4)
                    return False
            else:
                # For closer targets, use burst fire
                if self.shots_fired >= self.burst_size:
                    # Wait for burst delay before firing again
                    if now - self.last_shot_time < self.burst_delay * 0.7:  # Daha hızlı
                        return False
                    else:
                        # Reset burst counter after delay
                        self.shots_fired = 0
        
        # Return final decision
        return precise_aim
    
    def aim_at_target(self, frame, return_annotated=False):
        """Main function to detect, aim, and shoot at targets"""
        if self.model is None:
            return None
            
        # Get frame dimensions
        frame_height, frame_width = frame.shape[:2]
        
        # Detect all potential targets
        targets = self.detect_targets(frame)
        
        # Select best target using enhanced criteria
        best_target = self.select_best_target(targets, frame_width, frame_height, frame)
        
        # If we found a valid target
        if best_target:
            # Calculate ideal aim point with prediction
            delta_x, delta_y = self.calculate_aim_point(best_target, frame_width, frame_height)
            
            # Log aiming information
            print(f"Aiming: Moving mouse by dx={delta_x}, dy={delta_y}")
            
            # Smooth aim movement for human-like motion
            if abs(delta_x) > 1 or abs(delta_y) > 1:  # Only move if significant distance
                try:
                    # Doğrudan mouse kontrolü için daha güvenilir 
                    self.mouse_move(delta_x, delta_y)
                    print(f"Mouse moved by: {delta_x}, {delta_y}")
                    
                    # Small delay for aim to settle
                    time.sleep(self.aim_delay)
                except Exception as e:
                    print(f"Mouse movement error: {e}")
            
            # Decide whether to shoot
            should_shoot = self.should_fire(best_target, frame_width, frame_height)
            if should_shoot and self.auto_shoot:
                print("FIRING!")
                try:
                    # Shoot at target
                    self.mouse_click()
                    print("Shot fired")
                    
                    # Apply recoil control after shooting
                    if self.recoil_control_active:
                        self.apply_recoil_control()
                except Exception as e:
                    print(f"Mouse click error: {e}")
        
        # If requested, return annotated frame for visualization
        if return_annotated and targets:
            # Draw bounding boxes and aim points
            annotated = frame.copy()
            
            # Best target id for comparison
            best_target_id = best_target["index"] if best_target else -1
            
            for i, target in enumerate(targets):
                x1, y1, x2, y2 = [int(coord) for coord in target["xyxy"]]
                confidence = target["confidence"]
                
                # Draw bounding box
                color = (0, 255, 0) if i == best_target_id else (0, 0, 255)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                
                # Draw confidence
                cv2.putText(annotated, f"{confidence:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
            # Draw crosshair
            cv2.line(annotated, (frame_width//2 - 10, frame_height//2), 
                    (frame_width//2 + 10, frame_height//2), (0, 255, 255), 1)
            cv2.line(annotated, (frame_width//2, frame_height//2 - 10), 
                    (frame_width//2, frame_height//2 + 10), (0, 255, 255), 1)
            
            return annotated
            
        return None

# Example usage if run as standalone
if __name__ == "__main__":
    print("CS2 Aimbot v2.0 - DirectInput Edition")
    print("======================================")
    print("F1: Toggle Aimbot (Start/Stop)")
    print("F2: Toggle Auto-Shooting")
    print("F3: Increase Sensitivity")
    print("F4: Decrease Sensitivity")
    print("F5: Toggle Debug Visualization")
    print("F6: Toggle DirectInput Mode (Direct to Game)")
    print("Ctrl+C: Exit Program")
    print("======================================")
    
    # Initialize aimbot
    aimbot = CS2Aimbot(model_path=r"runs\detect\cs2_model2\weights\best.pt")
    # Düşük güven eşiği ile daha fazla obje algılayalım
    aimbot.confidence_threshold = 0.25
    
    # Screen capture setup
    sct = mss.mss()
    monitor = {
        "top": 0, 
        "left": 0, 
        "width": 1920, 
        "height": 1080
    }
    
    # Control variables
    running = True
    aimbot_enabled = True
    debug_mode = True
    directinput_mode = True  # Doğrudan oyuna girdi gönderme modu
    
    # Main loop
    try:
        print("Aimbot running... Press Ctrl+C to stop")
        print("Waiting for CS2 window...")
        
        while running:
            # CS2 penceresini kontrol et
            cs2_hwnd = InputEmulator.get_cs2_window()
            if cs2_hwnd == 0:
                print("CS2 penceresi bulunamadı! CS2'yi başlatın ve tekrar deneyin.")
                time.sleep(3)
                continue
            else:
                print(f"CS2 penceresi bulundu (HWND: {cs2_hwnd})")
            
            # Check keyboard controls
            if keyboard.is_pressed('f1'):
                aimbot_enabled = not aimbot_enabled
                print(f"Aimbot {'enabled' if aimbot_enabled else 'disabled'}")
                time.sleep(0.3)  # Prevent multiple toggles
                
            if keyboard.is_pressed('f2'):
                aimbot.auto_shoot = not aimbot.auto_shoot
                print(f"Auto-shooting {'enabled' if aimbot.auto_shoot else 'disabled'}")
                time.sleep(0.3)
                
            if keyboard.is_pressed('f3'):
                aimbot.aim_speed += 0.1
                print(f"Sensitivity increased to {aimbot.aim_speed:.1f}")
                time.sleep(0.2)
                
            if keyboard.is_pressed('f4'):
                aimbot.aim_speed = max(0.1, aimbot.aim_speed - 0.1)
                print(f"Sensitivity decreased to {aimbot.aim_speed:.1f}")
                time.sleep(0.2)
                
            if keyboard.is_pressed('f5'):
                debug_mode = not debug_mode
                print(f"Debug visualization {'enabled' if debug_mode else 'disabled'}")
                time.sleep(0.3)
            
            if keyboard.is_pressed('f6'):
                directinput_mode = not directinput_mode
                print(f"DirectInput mode {'enabled' if directinput_mode else 'disabled'}")
                time.sleep(0.3)
            
            # Capture screen
            frame = np.array(sct.grab(monitor))
            
            # Process frame if aimbot is enabled
            if aimbot_enabled:
                result = aimbot.aim_at_target(frame, return_annotated=debug_mode)
                
                # Show result for debugging
                if debug_mode and result is not None:
                    cv2.imshow("CS2 Aimbot Debug", result)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            # Limit processing rate
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("Aimbot stopped by user")
    
    finally:
        cv2.destroyAllWindows() 