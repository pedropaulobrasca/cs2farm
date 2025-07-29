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
from ultralytics import YOLO

class CS2Bot:
    def __init__(self):
        # Configuration
        self.model_path = r"runs\detect\cs2_model2\weights\best.pt"
        self.confidence_threshold = 0.4
        self.running = False
        self.paused = False
        self.screen_width, self.screen_height = pyautogui.size()
        self.center_x, self.center_y = self.screen_width // 2, self.screen_height // 2
        
        # Settings - adjust these based on your game sensitivity
        self.rotation_speed = 1.0
        self.aim_speed = 0.5
        self.fov_x, self.fov_y = 70, 40  # Detection field of view (% of screen)
        self.headshot_offset = -10  # Vertical offset for headshots (negative = higher)
        
        # Scanning control
        self.scanning = False
        self.scan_direction = 1  # 1 for right, -1 for left
        self.scan_angle = 0
        
        # Initialize the YOLOv8 model
        self.load_model()
        
        # Screen capture setup
        self.sct = mss.mss()
        self.monitor = {
            "top": int(self.center_y - self.screen_height * self.fov_y / 200),
            "left": int(self.center_x - self.screen_width * self.fov_x / 200),
            "width": int(self.screen_width * self.fov_x / 100),
            "height": int(self.screen_height * self.fov_y / 100)
        }
        
        # Performance monitoring
        self.fps = 0
        self.last_time = time.time()
        self.frame_count = 0
        
        print("CS2 Bot initialized")
        
    def load_model(self):
        """Load the YOLOv8 model for player detection"""
        try:
            self.model = YOLO(self.model_path)
            print(f"Model loaded from {self.model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None
        
    def mouse_move(self, dx, dy):
        """Move the mouse by the specified delta with smoothing"""
        # Scale the movement based on aim speed
        dx = int(dx * self.aim_speed)
        dy = int(dy * self.aim_speed)
        
        # Apply the movement
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)
    
    def mouse_click(self):
        """Click the left mouse button to shoot"""
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)  # Hold for a short time
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    def scan_for_enemies(self):
        """Rotate the camera to scan for enemies"""
        if not self.scanning:
            return
            
        # Calculate rotation amount based on speed and time
        rotation_amount = self.rotation_speed * 5
        
        # Apply rotation based on direction
        self.mouse_move(rotation_amount * self.scan_direction, 0)
        
        # Update scan angle
        self.scan_angle += rotation_amount * self.scan_direction
        
        # Change direction if we've rotated too far
        if abs(self.scan_angle) > 170:
            self.scan_direction *= -1
            self.scan_angle = 170 * self.scan_direction
    
    def detect_and_aim(self):
        """Capture screen, detect players, and aim at the closest one"""
        # Capture screen
        img = np.array(self.sct.grab(self.monitor))
        
        # Convert to RGB for YOLOv8
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        
        # Run YOLOv8 inference
        if self.model is not None:
            results = self.model(img_rgb, conf=self.confidence_threshold)[0]
            
            # Stop scanning if we found enemies
            if len(results.boxes) > 0:
                self.scanning = False
                
                # Find the closest target to center
                closest_dist = float('inf')
                target_x, target_y = 0, 0
                
                for box in results.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # Calculate center of bounding box
                    box_center_x = (x1 + x2) / 2
                    box_center_y = (y1 + y2) / 2
                    
                    # Calculate distance from screen center
                    dx = box_center_x - img_rgb.shape[1] / 2
                    dy = box_center_y - img_rgb.shape[0] / 2
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    if dist < closest_dist:
                        closest_dist = dist
                        target_x = dx
                        # Apply headshot offset - aim higher on the body
                        target_y = dy + self.headshot_offset
                
                # Convert target coordinates to screen coordinates
                screen_x = target_x
                screen_y = target_y
                
                # Aim at the target
                if abs(screen_x) > 5 or abs(screen_y) > 5:  # Only move if significant distance
                    self.mouse_move(int(screen_x), int(screen_y))
                    # Small delay to allow aim to settle
                    time.sleep(0.05)
                
                # If we're very close to target, shoot
                if abs(screen_x) < 10 and abs(screen_y) < 10:
                    self.mouse_click()
                    time.sleep(0.1)  # Small delay after shooting
            else:
                # If no enemies found, continue scanning
                self.scanning = True
        
        # Calculate FPS
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_time >= 1:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_time = current_time
            print(f"FPS: {self.fps}")
        
        # You can draw on the image for debugging, e.g.:
        # cv2.imshow("CS2Bot Vision", img_rgb)
        # cv2.waitKey(1)
    
    def start(self):
        """Start the bot"""
        print("Starting CS2Bot - Press 'F8' to stop, 'F7' to pause/resume")
        self.running = True
        self.scanning = True
        
        while self.running:
            try:
                # Check for stop key
                if keyboard.is_pressed('f8'):
                    self.running = False
                    print("Bot stopped")
                    break
                
                # Check for pause key
                if keyboard.is_pressed('f7'):
                    self.paused = not self.paused
                    print(f"Bot {'paused' if self.paused else 'resumed'}")
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
                print(f"Error: {e}")
                time.sleep(0.1)
                
        # Clean up
        cv2.destroyAllWindows()
        
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
    bot = CS2Bot()
    bot.start() 