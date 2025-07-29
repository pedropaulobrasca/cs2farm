import cv2
import numpy as np
import time
import torch
import win32api, win32con, win32gui
import pyautogui
import keyboard
import mss
import math
import os
import threading
import json
from ultralytics import YOLO
from datetime import datetime

class CS2AdvancedBot:
    def __init__(self, config_file="bot_config.json"):
        # Load configuration from file if it exists
        self.config_file = config_file
        self.load_config()
        
        # Screen properties
        self.screen_width, self.screen_height = pyautogui.size()
        self.center_x, self.center_y = self.screen_width // 2, self.screen_height // 2
        
        # Runtime variables
        self.running = False
        self.paused = False
        self.scanning = False
        self.scan_direction = 1
        self.scan_angle = 0
        self.target_lock = False
        self.current_target = None
        self.shots_fired = 0
        self.recoil_stage = 0
        self.last_shot_time = 0
        
        # Statistics
        self.kills = 0
        self.shots = 0
        self.hits = 0
        self.start_time = None
        self.session_xp = 0
        
        # Initialize YOLOv8 model
        self.load_model()
        
        # Screen capture setup
        self.sct = mss.mss()
        self.update_monitor_region()
        
        # Performance monitoring
        self.fps = 0
        self.last_time = time.time()
        self.frame_count = 0
        
        # Create log directory
        os.makedirs("logs", exist_ok=True)
        self.log_file = f"logs/cs2bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        self.log("CS2 Advanced Bot initialized")
        
    def load_config(self):
        """Load configuration from file or use defaults"""
        default_config = {
            "model_path": r"runs\detect\cs2_model2\weights\best.pt",
            "confidence_threshold": 0.4,
            "rotation_speed": 1.0,
            "aim_speed": 0.5,
            "fov_x": 70,
            "fov_y": 40,
            "headshot_offset": -10,
            "aim_smoothness": 2.0,
            "recoil_control": True,
            "target_enemies_only": True,
            "burst_fire": True,
            "burst_size": 3,
            "burst_delay": 0.3,
            "auto_reload": True,
            "reload_ammo_threshold": 5,
            "hotkeys": {
                "toggle": "f6",
                "pause": "f7",
                "stop": "f8"
            }
        }
        
        # Try to load from file
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    
                # Update default config with loaded values
                for key, value in loaded_config.items():
                    default_config[key] = value
                    
                self.log(f"Configuration loaded from {self.config_file}")
        except Exception as e:
            self.log(f"Error loading config: {e}. Using defaults.")
        
        # Set configuration attributes
        for key, value in default_config.items():
            setattr(self, key, value)
        
        # Save config back to file
        self.save_config()
        
    def save_config(self):
        """Save current configuration to file"""
        config = {
            "model_path": self.model_path,
            "confidence_threshold": self.confidence_threshold,
            "rotation_speed": self.rotation_speed,
            "aim_speed": self.aim_speed,
            "fov_x": self.fov_x,
            "fov_y": self.fov_y,
            "headshot_offset": self.headshot_offset,
            "aim_smoothness": self.aim_smoothness,
            "recoil_control": self.recoil_control,
            "target_enemies_only": self.target_enemies_only,
            "burst_fire": self.burst_fire,
            "burst_size": self.burst_size,
            "burst_delay": self.burst_delay,
            "auto_reload": self.auto_reload,
            "reload_ammo_threshold": self.reload_ammo_threshold,
            "hotkeys": self.hotkeys
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            self.log(f"Error saving config: {e}")
    
    def update_monitor_region(self):
        """Update the screen region to capture based on FOV settings"""
        self.monitor = {
            "top": int(self.center_y - self.screen_height * self.fov_y / 200),
            "left": int(self.center_x - self.screen_width * self.fov_x / 200),
            "width": int(self.screen_width * self.fov_x / 100),
            "height": int(self.screen_height * self.fov_y / 100)
        }
    
    def load_model(self):
        """Load the YOLOv8 model for player detection"""
        try:
            self.model = YOLO(self.model_path)
            self.log(f"Model loaded from {self.model_path}")
        except Exception as e:
            self.log(f"Error loading model: {e}")
            self.model = None
    
    def log(self, message):
        """Log a message to console and log file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + "\n")
        except:
            pass
    
    def mouse_move(self, dx, dy, smooth=True):
        """Move mouse with optional smoothing for more natural movement"""
        if smooth and self.aim_smoothness > 1.0:
            # Divide movement into smaller steps
            steps = int(self.aim_smoothness)
            step_x = dx / steps
            step_y = dy / steps
            
            for _ in range(steps):
                # Scale by aim speed
                move_x = int(step_x * self.aim_speed)
                move_y = int(step_y * self.aim_speed)
                
                if move_x != 0 or move_y != 0:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
                    time.sleep(0.001)  # Small delay between movements
        else:
            # Single movement scaled by aim speed
            move_x = int(dx * self.aim_speed)
            move_y = int(dy * self.aim_speed)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
    
    def mouse_click(self):
        """Click the left mouse button to shoot"""
        now = time.time()
        self.shots += 1
        self.shots_fired += 1
        self.last_shot_time = now
        
        # Apply left mouse down/up events
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        
        # Apply recoil control if enabled
        if self.recoil_control:
            self.apply_recoil_control()
    
    def apply_recoil_control(self):
        """Apply recoil compensation based on weapon type and shots fired"""
        # This is a simplified recoil pattern for CS2 rifles (like AK-47)
        # Adjust this for different weapons or based on game testing
        
        if self.shots_fired <= 3:
            # First few shots - slight upward recoil
            self.mouse_move(0, -3, smooth=False)
        elif self.shots_fired <= 10:
            # Middle shots - stronger upward + side recoil
            self.mouse_move(
                -2 if self.shots_fired % 2 == 0 else 2,  # Alternating left-right
                -4,  # Upward compensation
                smooth=False
            )
        else:
            # Later shots - complex pattern
            # Simplified based on common rifle spray patterns
            angle = math.sin(self.shots_fired * 0.5) * 3
            self.mouse_move(int(angle), -5, smooth=False)
    
    def reload(self):
        """Simulate pressing R key to reload"""
        self.log("Reloading weapon")
        win32api.keybd_event(0x52, 0, 0, 0)  # R key down
        time.sleep(0.05)
        win32api.keybd_event(0x52, 0, win32con.KEYEVENTF_KEYUP, 0)  # R key up
        
        # Reset shots counter
        self.shots_fired = 0
        time.sleep(0.1)  # Small delay after reload command
    
    def scan_for_enemies(self):
        """Rotate the camera to scan for enemies"""
        if not self.scanning:
            return
            
        # Calculate rotation amount based on speed and time
        rotation_amount = self.rotation_speed * 5
        
        # Apply rotation based on direction
        self.mouse_move(rotation_amount * self.scan_direction, 0, smooth=False)
        
        # Update scan angle
        self.scan_angle += rotation_amount * self.scan_direction
        
        # Change direction if we've rotated too far
        if abs(self.scan_angle) > 170:
            self.scan_direction *= -1
            self.scan_angle = 170 * self.scan_direction
    
    def select_best_target(self, boxes, classes, confs):
        """Select the best target based on priority criteria"""
        if len(boxes) == 0:
            return None
            
        targets = []
        
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box.tolist()
            conf = confs[i]
            cls = int(classes[i])
            
            # Calculate center of bounding box
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Calculate distance from screen center
            dx = center_x - self.monitor["width"] / 2
            dy = center_y - self.monitor["height"] / 2
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Calculate box size (larger targets are closer)
            size = (x2 - x1) * (y2 - y1)
            
            # Calculate target priority score (lower is better)
            # Factors: distance to crosshair, confidence, size
            priority = distance * 0.5 - size * 0.0001 - conf * 10
            
            targets.append({
                "index": i,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "center_x": center_x, "center_y": center_y,
                "dx": dx, "dy": dy,
                "distance": distance,
                "size": size,
                "conf": conf,
                "class": cls,
                "priority": priority
            })
        
        # Sort targets by priority (lower is better)
        targets.sort(key=lambda t: t["priority"])
        
        # Return the best target
        return targets[0]
    
    def detect_and_aim(self):
        """Capture screen, detect players, and aim at the best target"""
        # Capture screen
        img = np.array(self.sct.grab(self.monitor))
        
        # Convert to RGB for YOLOv8
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        
        # Run YOLOv8 inference
        if self.model is not None:
            results = self.model(img_rgb, conf=self.confidence_threshold)[0]
            
            if len(results.boxes) > 0:
                # Get detection data
                boxes = results.boxes.xyxy
                classes = results.boxes.cls
                confs = results.boxes.conf
                
                # Select best target
                target = self.select_best_target(boxes, classes, confs)
                
                if target:
                    # Stop scanning when target found
                    self.scanning = False
                    
                    # Calculate aim target (with headshot offset)
                    target_x = target["dx"]
                    target_y = target["dy"] + self.headshot_offset
                    
                    # Aim at target if it's far enough from center
                    if abs(target_x) > 3 or abs(target_y) > 3:
                        self.mouse_move(int(target_x), int(target_y))
                    
                    # Once aim is on target
                    if abs(target_x) < 10 and abs(target_y) < 10:
                        # Check if we should shoot
                        now = time.time()
                        should_shoot = True
                        
                        # Apply burst fire logic if enabled
                        if self.burst_fire:
                            if self.shots_fired >= self.burst_size:
                                # Wait for burst delay before firing again
                                if now - self.last_shot_time < self.burst_delay:
                                    should_shoot = False
                                else:
                                    # Reset burst counter after delay
                                    self.shots_fired = 0
                        
                        # Shoot if conditions are met
                        if should_shoot:
                            self.mouse_click()
                            self.hits += 1  # Assuming a hit when aimed correctly
                            
                            # Check if we need to reload
                            if self.auto_reload and self.shots_fired > self.reload_ammo_threshold:
                                self.reload()
                else:
                    # Reset if no valid target
                    self.scanning = True
                    self.shots_fired = 0
            else:
                # No detections, scan for enemies
                self.scanning = True
                self.shots_fired = 0
        
        # Update performance stats
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_time >= 1:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_time = current_time
            self.log(f"FPS: {self.fps}, Shots: {self.shots}, Hits: {self.hits}")
    
    def start(self):
        """Start the bot"""
        self.log(f"Starting CS2 Advanced Bot - Press '{self.hotkeys['stop']}' to stop, '{self.hotkeys['pause']}' to pause/resume")
        
        self.running = True
        self.scanning = True
        self.start_time = time.time()
        
        while self.running:
            try:
                # Check for stop key
                if keyboard.is_pressed(self.hotkeys['stop']):
                    self.running = False
                    self.log("Bot stopped by user")
                    break
                
                # Check for pause key
                if keyboard.is_pressed(self.hotkeys['pause']):
                    self.paused = not self.paused
                    self.log(f"Bot {'paused' if self.paused else 'resumed'} by user")
                    time.sleep(0.5)  # Prevent multiple toggles
                
                # Skip processing if paused
                if self.paused:
                    time.sleep(0.1)
                    continue
                
                # Main bot logic
                self.detect_and_aim()
                
                # If not targeting, scan for enemies
                if self.scanning:
                    self.scan_for_enemies()
                
                # Small sleep to control CPU usage
                time.sleep(0.01)
                
            except Exception as e:
                self.log(f"Error in main loop: {e}")
                time.sleep(0.1)
        
        # Clean up and save stats
        self.save_session_stats()
        cv2.destroyAllWindows()
    
    def save_session_stats(self):
        """Save session statistics to file"""
        if self.start_time:
            session_duration = time.time() - self.start_time
            
            stats = {
                "session_start": datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
                "session_end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": round(session_duration, 2),
                "duration_formatted": f"{int(session_duration//3600):02d}:{int((session_duration%3600)//60):02d}:{int(session_duration%60):02d}",
                "kills": self.kills,
                "shots": self.shots,
                "hits": self.hits,
                "accuracy": round(self.hits / max(1, self.shots) * 100, 2),
                "xp_gained": self.session_xp
            }
            
            try:
                stats_file = f"logs/stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(stats_file, 'w') as f:
                    json.dump(stats, f, indent=4)
                self.log(f"Session stats saved to {stats_file}")
                
                # Log summary
                self.log(f"Session summary: Duration: {stats['duration_formatted']}, Shots: {stats['shots']}, Hits: {stats['hits']}, Accuracy: {stats['accuracy']}%")
            except Exception as e:
                self.log(f"Error saving stats: {e}")
    
    def run_in_thread(self):
        """Run the bot in a separate thread"""
        thread = threading.Thread(target=self.start)
        thread.daemon = True
        thread.start()
        return thread

if __name__ == "__main__":
    # Allow time to switch to the game window
    print("Switch to CS2 game window in 5 seconds...")
    time.sleep(5)
    
    # Create and start the bot
    bot = CS2AdvancedBot()
    bot.start() 