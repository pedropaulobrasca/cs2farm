import argparse
import json
import logging
import os
import platform
import random
import sys
import threading
import time
import uuid
from datetime import datetime
import subprocess
import requests
import psutil
import win32gui
import win32process
import win32con
import win32api
import pyautogui
import mss
import numpy as np
import cv2
from pathlib import Path

# Botları doğru şekilde import edebilmek için modül yolunu ayarlıyoruz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from cs2_aimbot import CS2Aimbot
    from cs2_advanced_bot import CS2AdvancedBot
except ImportError:
    print("UYARI: Bot modülleri bulunamadı, gerekirse indirilecek.")

# Temel yapılandırma
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_config.json')
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')

# Dizinleri oluştur
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Log yapılandırması
log_file = os.path.join(LOG_DIR, f'client_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FarmLabsClient")

class CS2Client:
    def __init__(self, server_url, api_key, vm_id=None):
        self.server_url = server_url
        self.api_key = api_key
        self.vm_id = vm_id if vm_id else str(uuid.uuid4())
        self.config = self.load_config()
        self.machine_name = platform.node()
        self.running = False
        self.active_job = None
        self.bot_instance = None
        self.steam_process = None
        self.cs2_process = None
        
        self.sct = mss.mss()
        self.last_heartbeat = 0
        self.heartbeat_interval = 30  # saniye
        
        # Bot durumu
        self.bot_status = 'inactive'
        self.current_xp = 0
        self.current_level = 0
        self.session_start_time = None
        
        logger.info(f"CS2 Client başlatıldı - Machine: {self.machine_name}, VM ID: {self.vm_id}")
    
    def load_config(self):
        """Yapılandırma dosyasını yükle veya oluştur"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    
                # VM ID'yi güncelleştir
                if self.vm_id and 'vm_id' in config:
                    config['vm_id'] = self.vm_id
                    
                return config
            except Exception as e:
                logger.error(f"Yapılandırma dosyası yüklenirken hata oluştu: {e}")
        
        # Varsayılan yapılandırma
        default_config = {
            'vm_id': self.vm_id,
            'server_url': self.server_url,
            'api_key': self.api_key,
            'steam_path': r'C:\Program Files (x86)\Steam\steam.exe',
            'cs2_app_id': 730,
            'bot_type': 'advanced',  # 'aimbot' veya 'advanced'
            'screenshot_interval': 300,  # saniye
            'max_session_time': 10800,  # 3 saat
            'auto_restart': True
        }
        
        # Yapılandırmayı kaydet
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config=None):
        """Yapılandırmayı dosyaya kaydet"""
        if config is None:
            config = self.config
            
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Yapılandırma kaydedilirken hata oluştu: {e}")
            return False
    
    def send_heartbeat(self):
        """Sunucuya durum bildirimi gönder"""
        current_time = time.time()
        
        # Heartbeat gönderme aralığını kontrol et
        if current_time - self.last_heartbeat < self.heartbeat_interval:
            return
            
        self.last_heartbeat = current_time
        
        try:
            url = f"{self.server_url}/api/v1/heartbeat"
            headers = {'Content-Type': 'application/json', 'X-API-Key': self.api_key}
            data = {
                'vm_id': self.vm_id,
                'machine_name': self.machine_name,
                'status': self.bot_status,
                'timestamp': datetime.now().isoformat(),
                'job_id': self.active_job['id'] if self.active_job else None,
                'cs2_running': self.cs2_process is not None,
                'steam_running': self.steam_process is not None,
                'current_xp': self.current_xp,
                'current_level': self.current_level
            }
            
            logger.debug("Heartbeat gönderiliyor...")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                logger.debug(f"Heartbeat başarılı: {response_data}")
                
                # Yeni iş var mı kontrol et
                if response_data.get('has_jobs', False) and not self.active_job:
                    pending_jobs = response_data.get('pending_jobs', [])
                    if pending_jobs:
                        # İlk bekleyen işi al
                        self.active_job = pending_jobs[0]
                        logger.info(f"Yeni iş alındı: {self.active_job['id']} - Tip: {self.active_job['type']}")
                        
                        # İşi başlat
                        self.start_job(self.active_job)
            else:
                logger.error(f"Heartbeat hatası: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.error(f"Heartbeat gönderilirken hata oluştu: {e}")
    
    def get_bot_config(self):
        """Sunucudan bot yapılandırmasını al"""
        try:
            url = f"{self.server_url}/api/v1/bot/config/{self.vm_id}"
            headers = {'Content-Type': 'application/json', 'X-API-Key': self.api_key}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                config = response.json()
                logger.info("Bot yapılandırması alındı")
                return config
            else:
                logger.error(f"Bot yapılandırması alınamadı: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Bot yapılandırması alınırken hata oluştu: {e}")
            return None
    
    def update_job_status(self, job_id, updates):
        """İş durumunu sunucuda güncelle"""
        try:
            url = f"{self.server_url}/api/v1/job/update"
            headers = {'Content-Type': 'application/json', 'X-API-Key': self.api_key}
            data = {
                'job_id': job_id,
                'job_type': 'bot',
                'updates': updates
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"İş durumu güncellendi: {job_id}")
                return True
            else:
                logger.error(f"İş durumu güncellenemedi: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"İş durumu güncellenirken hata oluştu: {e}")
            return False
    
    def is_steam_running(self):
        """Steam'in çalışıp çalışmadığını kontrol et"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'steam' in proc.info['name'].lower():
                    self.steam_process = proc
                    return True
            
            self.steam_process = None
            return False
        except Exception as e:
            logger.error(f"Steam durumu kontrol edilirken hata oluştu: {e}")
            return False
    
    def is_cs2_running(self):
        """CS2'nin çalışıp çalışmadığını kontrol et"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                # CS2 işlem adı
                if 'cs2' in proc.info['name'].lower() or 'counter-strike' in proc.info['name'].lower():
                    self.cs2_process = proc
                    return True
            
            self.cs2_process = None
            return False
        except Exception as e:
            logger.error(f"CS2 durumu kontrol edilirken hata oluştu: {e}")
            return False
    
    def start_steam(self):
        """Steam'i başlat"""
        if self.is_steam_running():
            logger.info("Steam zaten çalışıyor")
            return True
        
        try:
            steam_path = self.config.get('steam_path', r'C:\Program Files (x86)\Steam\steam.exe')
            logger.info(f"Steam başlatılıyor: {steam_path}")
            
            # Steam'i başlat
            subprocess.Popen([steam_path, "-silent"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            # Steam'in başlamasını bekle
            max_wait = 60  # saniye
            start_time = time.time()
            
            while not self.is_steam_running():
                if time.time() - start_time > max_wait:
                    logger.error("Steam başlatılamadı - zaman aşımı")
                    return False
                
                logger.info("Steam başlatılıyor, bekleniyor...")
                time.sleep(5)
            
            logger.info("Steam başarıyla başlatıldı")
            return True
        
        except Exception as e:
            logger.error(f"Steam başlatılırken hata oluştu: {e}")
            return False
    
    def start_cs2(self):
        """CS2'yi Steam üzerinden başlat"""
        if self.is_cs2_running():
            logger.info("CS2 zaten çalışıyor")
            return True
        
        if not self.is_steam_running():
            if not self.start_steam():
                logger.error("CS2 başlatılamadı - Steam çalışmıyor")
                return False
        
        try:
            # Steam üzerinden CS2'yi başlat
            cs2_app_id = self.config.get('cs2_app_id', 730)
            logger.info(f"CS2 başlatılıyor (AppID: {cs2_app_id})")
            
            # Steam URL protokolü ile CS2'yi başlat
            subprocess.Popen([f"steam://run/{cs2_app_id}"], shell=True)
            
            # CS2'nin başlamasını bekle
            max_wait = 120  # saniye
            start_time = time.time()
            
            while not self.is_cs2_running():
                if time.time() - start_time > max_wait:
                    logger.error("CS2 başlatılamadı - zaman aşımı")
                    return False
                
                logger.info("CS2 başlatılıyor, bekleniyor...")
                time.sleep(5)
            
            # Oyunun tam yüklenmesi için biraz daha bekle
            logger.info("CS2 başlatıldı, oyunun tam yüklenmesi bekleniyor...")
            time.sleep(30)
            
            # CS2 penceresini öne getir
            self.focus_cs2_window()
            
            logger.info("CS2 başarıyla başlatıldı")
            return True
        
        except Exception as e:
            logger.error(f"CS2 başlatılırken hata oluştu: {e}")
            return False
    
    def focus_cs2_window(self):
        """CS2 penceresini öne getir"""
        try:
            def callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    if "counter-strike" in win32gui.GetWindowText(hwnd).lower():
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        return True
                return True
            
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.error(f"CS2 penceresi odaklanırken hata oluştu: {e}")
    
    def take_screenshot(self):
        """Ekran görüntüsü al ve kaydet"""
        try:
            # Ekran görüntüsü al
            monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
            screenshot = np.array(self.sct.grab(monitor))
            
            # Dosya adı oluştur
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(SCREENSHOTS_DIR, f"cs2_{timestamp}.jpg")
            
            # Kaydet
            cv2.imwrite(filename, screenshot)
            logger.info(f"Ekran görüntüsü kaydedildi: {filename}")
            
            return filename
        except Exception as e:
            logger.error(f"Ekran görüntüsü alınırken hata oluştu: {e}")
            return None
    
    def init_bot(self, bot_config=None):
        """Bot örneğini başlat"""
        if bot_config is None:
            bot_config = self.get_bot_config()
            
        if bot_config is None:
            logger.error("Bot yapılandırması alınamadı, varsayılan değerler kullanılacak")
            bot_config = {
                "model_path": r"runs\detect\cs2_model2\weights\best.pt",
                "confidence_threshold": 0.4,
                "rotation_speed": 1.0,
                "aim_speed": 0.5,
                "fov_x": 70,
                "fov_y": 40,
                "headshot_offset": -10,
                "aim_smoothness": 2.0
            }
        
        try:
            # Bot tipine göre örnek oluştur
            bot_type = self.config.get('bot_type', 'advanced')
            
            if bot_type == 'aimbot':
                logger.info("CS2Aimbot başlatılıyor...")
                self.bot_instance = CS2Aimbot(model_path=bot_config.get('model_path'))
                
                # Parametreleri güncelle
                for key, value in bot_config.items():
                    if hasattr(self.bot_instance, key):
                        setattr(self.bot_instance, key, value)
            else:
                # Advanced Bot
                logger.info("CS2AdvancedBot başlatılıyor...")
                self.bot_instance = CS2AdvancedBot(config_file=None)
                
                # Parametreleri doğrudan ayarla
                for key, value in bot_config.items():
                    if hasattr(self.bot_instance, key):
                        setattr(self.bot_instance, key, value)
            
            logger.info("Bot başarıyla başlatıldı")
            return True
        
        except Exception as e:
            logger.error(f"Bot başlatılırken hata oluştu: {e}")
            return False
    
    def run_bot(self):
        """Bot'u çalıştır"""
        if self.bot_instance is None:
            if not self.init_bot():
                return False
        
        # CS2 çalışıyor mu kontrol et
        if not self.is_cs2_running():
            if not self.start_cs2():
                return False
        
        # CS2 penceresini öne getir
        self.focus_cs2_window()
        
        # Bot tipine göre çalıştır
        try:
            if isinstance(self.bot_instance, CS2Aimbot):
                # Aimbot modunda çalıştır
                logger.info("CS2Aimbot çalıştırılıyor...")
                
                # Ekran görüntüsü yakalama döngüsü
                while self.running and self.is_cs2_running():
                    monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
                    frame = np.array(self.sct.grab(monitor))
                    
                    # Bot işlemleri
                    self.bot_instance.aim_at_target(frame)
                    
                    # Kısa bekleme
                    time.sleep(0.01)
            
            elif isinstance(self.bot_instance, CS2AdvancedBot):
                # Advanced bot modunda çalıştır
                logger.info("CS2AdvancedBot çalıştırılıyor...")
                
                # Doğrudan start metodu ile çalıştır
                self.bot_instance.running = True
                self.bot_instance.scanning = True
                self.bot_instance.start_time = time.time()
                
                # Bot döngüsü
                while self.running and self.is_cs2_running():
                    try:
                        # Durdurma tuşu kontrolü
                        if win32api.GetAsyncKeyState(win32con.VK_F8) & 0x8000:
                            logger.info("F8 tuşu ile durduruldu")
                            break
                        
                        # Duraklatma tuşu kontrolü
                        if win32api.GetAsyncKeyState(win32con.VK_F7) & 0x8000:
                            self.bot_instance.paused = not self.bot_instance.paused
                            logger.info(f"Bot {'duraklatıldı' if self.bot_instance.paused else 'devam ediyor'}")
                            time.sleep(0.5)  # Çoklu basış engelle
                        
                        # Bot duraklatıldıysa atla
                        if self.bot_instance.paused:
                            time.sleep(0.1)
                            continue
                        
                        # Ana bot mantığı
                        self.bot_instance.detect_and_aim()
                        
                        # Tarama kontrolü
                        if self.bot_instance.scanning:
                            self.bot_instance.scan_for_enemies()
                        
                        # CPU kullanımını kontrol et
                        time.sleep(0.01)
                        
                    except Exception as e:
                        logger.error(f"Bot çalışırken hata oluştu: {e}")
                        time.sleep(0.1)
                
                # İstatistikleri güncelle
                self.current_xp = self.bot_instance.session_xp
                self.current_level = 0  # Bot'tan seviyeyi al
            
            else:
                logger.error("Desteklenmeyen bot türü")
                return False
            
            logger.info("Bot çalışması tamamlandı")
            return True
        
        except Exception as e:
            logger.error(f"Bot çalıştırılırken hata oluştu: {e}")
            return False
    
    def start_job(self, job):
        """Belirli bir işi başlat"""
        if job['type'] == 'xp_farm':
            return self.start_xp_farm_job(job)
        elif job['type'] == 'drop_screenshot':
            return self.start_screenshot_job(job)
        elif job['type'] == 'claim_drop':
            return self.start_claim_drop_job(job)
        else:
            logger.error(f"Desteklenmeyen iş türü: {job['type']}")
            return False
    
    def start_xp_farm_job(self, job):
        """XP farm işini başlat"""
        logger.info(f"XP Farm işi başlatılıyor: {job['id']}")
        
        # İş durumunu güncelle
        self.update_job_status(job['id'], {
            'status': 'running',
            'start_time': datetime.now().isoformat()
        })
        
        # Hedef XP ve seviye
        target_xp = job['params'].get('target_xp', 1000)
        target_level = job['params'].get('target_level', 20)
        
        logger.info(f"Hedef XP: {target_xp}, Hedef Seviye: {target_level}")
        
        # Bot'u başlat
        if self.bot_instance is None:
            if not self.init_bot():
                # İşi başarısız olarak işaretle
                self.update_job_status(job['id'], {
                    'status': 'failed',
                    'completion_time': datetime.now().isoformat(),
                    'result': {
                        'error': 'Bot başlatılamadı'
                    }
                })
                return False
        
        # CS2'yi başlat
        if not self.is_cs2_running():
            if not self.start_cs2():
                # İşi başarısız olarak işaretle
                self.update_job_status(job['id'], {
                    'status': 'failed',
                    'completion_time': datetime.now().isoformat(),
                    'result': {
                        'error': 'CS2 başlatılamadı'
                    }
                })
                return False
        
        # Bot'un çalışmasına izin ver
        self.running = True
        self.bot_status = 'running'
        self.session_start_time = time.time()
        
        # Bot'u ayrı bir thread'de çalıştır
        bot_thread = threading.Thread(target=self.run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        
        # Maksimum çalışma süresi için zaman aşımı kontrolü
        max_session_time = self.config.get('max_session_time', 10800)  # 3 saat
        
        # İş tamamlanana kadar bekle
        while self.running and self.is_cs2_running():
            # Düzenli ekran görüntüsü al
            screenshot_interval = self.config.get('screenshot_interval', 300)  # 5 dakika
            if time.time() - self.session_start_time > screenshot_interval:
                self.take_screenshot()
                self.session_start_time = time.time()
            
            # Sunucuyla iletişim kur
            self.send_heartbeat()
            
            # Zaman aşımını kontrol et
            if time.time() - self.session_start_time > max_session_time:
                logger.info(f"Maksimum oturum süresi aşıldı ({max_session_time} saniye)")
                break
            
            # Hedefleri kontrol et
            if isinstance(self.bot_instance, CS2AdvancedBot):
                if self.bot_instance.session_xp >= target_xp:
                    logger.info(f"Hedef XP'ye ulaşıldı: {self.bot_instance.session_xp} >= {target_xp}")
                    break
            
            # Kısa bekleme
            time.sleep(10)
        
        # Bot'u durdur
        self.running = False
        self.bot_status = 'inactive'
        
        # İşi tamamlandı olarak işaretle
        self.update_job_status(job['id'], {
            'status': 'completed',
            'completion_time': datetime.now().isoformat(),
            'result': {
                'gained_xp': self.current_xp,
                'final_level': self.current_level,
                'session_duration': int(time.time() - self.session_start_time)
            }
        })
        
        logger.info(f"XP Farm işi tamamlandı: {job['id']}")
        
        # Aktif işi temizle
        self.active_job = None
        return True
    
    def start_screenshot_job(self, job):
        """Ekran görüntüsü alma işini başlat"""
        logger.info(f"Ekran görüntüsü işi başlatılıyor: {job['id']}")
        
        # İş durumunu güncelle
        self.update_job_status(job['id'], {
            'status': 'running',
            'start_time': datetime.now().isoformat()
        })
        
        # CS2'yi başlat
        if not self.is_cs2_running():
            if not self.start_cs2():
                # İşi başarısız olarak işaretle
                self.update_job_status(job['id'], {
                    'status': 'failed',
                    'completion_time': datetime.now().isoformat(),
                    'result': {
                        'error': 'CS2 başlatılamadı'
                    }
                })
                return False
        
        # CS2 penceresini öne getir
        self.focus_cs2_window()
        
        # 5 saniye bekle
        time.sleep(5)
        
        # Ekran görüntüsü al
        screenshot_path = self.take_screenshot()
        
        if screenshot_path:
            # İşi tamamlandı olarak işaretle
            self.update_job_status(job['id'], {
                'status': 'completed',
                'completion_time': datetime.now().isoformat(),
                'result': {
                    'screenshot_path': screenshot_path
                }
            })
            
            logger.info(f"Ekran görüntüsü işi tamamlandı: {job['id']}")
            
            # Aktif işi temizle
            self.active_job = None
            return True
        else:
            # İşi başarısız olarak işaretle
            self.update_job_status(job['id'], {
                'status': 'failed',
                'completion_time': datetime.now().isoformat(),
                'result': {
                    'error': 'Ekran görüntüsü alınamadı'
                }
            })
            
            logger.error(f"Ekran görüntüsü işi başarısız: {job['id']}")
            
            # Aktif işi temizle
            self.active_job = None
            return False
    
    def start_claim_drop_job(self, job):
        """Drop talep etme işini başlat"""
        logger.info(f"Drop talep işi başlatılıyor: {job['id']}")
        
        # İş durumunu güncelle
        self.update_job_status(job['id'], {
            'status': 'running',
            'start_time': datetime.now().isoformat()
        })
        
        # CS2'yi başlat
        if not self.is_cs2_running():
            if not self.start_cs2():
                # İşi başarısız olarak işaretle
                self.update_job_status(job['id'], {
                    'status': 'failed',
                    'completion_time': datetime.now().isoformat(),
                    'result': {
                        'error': 'CS2 başlatılamadı'
                    }
                })
                return False
        
        # CS2 penceresini öne getir
        self.focus_cs2_window()
        
        try:
            # Drop menüsüne gitme işlemleri
            # Not: Bu kısım CS2 arayüzüne göre özelleştirilmeli
            
            # Inventory menüsüne tıkla
            pyautogui.click(x=600, y=50)
            time.sleep(2)
            
            # Drops sekmesine tıkla
            pyautogui.click(x=800, y=150)
            time.sleep(2)
            
            # Claim butonuna tıkla
            pyautogui.click(x=700, y=500)
            time.sleep(3)
            
            # Ekran görüntüsü al
            screenshot_path = self.take_screenshot()
            
            # İşi tamamlandı olarak işaretle
            self.update_job_status(job['id'], {
                'status': 'completed',
                'completion_time': datetime.now().isoformat(),
                'result': {
                    'screenshot_path': screenshot_path,
                    'claimed': True
                }
            })
            
            logger.info(f"Drop talep işi tamamlandı: {job['id']}")
            
            # Aktif işi temizle
            self.active_job = None
            return True
            
        except Exception as e:
            logger.error(f"Drop talep edilirken hata oluştu: {e}")
            
            # İşi başarısız olarak işaretle
            self.update_job_status(job['id'], {
                'status': 'failed',
                'completion_time': datetime.now().isoformat(),
                'result': {
                    'error': f'Drop talep edilirken hata: {str(e)}'
                }
            })
            
            # Aktif işi temizle
            self.active_job = None
            return False
    
    def run(self):
        """Ana istemci döngüsünü çalıştır"""
        logger.info("CS2 Client başlatılıyor...")
        
        try:
            while True:
                # Steam ve CS2 durumlarını kontrol et
                self.is_steam_running()
                self.is_cs2_running()
                
                # Sunucuyla iletişim kur
                self.send_heartbeat()
                
                # Aktif iş yok ve CS2 çalışmıyorsa, boşta bekle
                if not self.active_job and not self.cs2_process:
                    time.sleep(10)
                    continue
                
                # Aktif iş varsa ve CS2 çalışmıyorsa, CS2'yi başlat
                if self.active_job and not self.cs2_process:
                    if not self.start_cs2():
                        logger.error("CS2 başlatılamadı, iş bekliyor")
                        time.sleep(30)
                        continue
                
                # 10 saniye bekle
                time.sleep(10)
        
        except KeyboardInterrupt:
            logger.info("Kullanıcı tarafından durduruldu")
        
        except Exception as e:
            logger.error(f"Ana döngüde hata oluştu: {e}")
        
        finally:
            logger.info("CS2 Client kapatılıyor...")
            
            # Aktif iş varsa, sonlandır
            if self.active_job:
                self.update_job_status(self.active_job['id'], {
                    'status': 'interrupted',
                    'completion_time': datetime.now().isoformat(),
                    'result': {
                        'error': 'Client kapatıldı'
                    }
                })
            
            # Bot'u durdur
            self.running = False
            self.bot_status = 'inactive'
            
            # mss kaynağını temizle
            self.sct.close()

def main():
    parser = argparse.ArgumentParser(description='CS2 FarmLabs Client')
    parser.add_argument('--server', help='Sunucu URL', default='http://127.0.0.1:8000')
    parser.add_argument('--api-key', help='API Anahtarı', required=True)
    parser.add_argument('--vm-id', help='VM ID', default=None)
    
    args = parser.parse_args()
    
    client = CS2Client(args.server, args.api_key, args.vm_id)
    client.run()

if __name__ == "__main__":
    main() 