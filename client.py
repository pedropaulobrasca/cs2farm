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

# Ajustando o caminho do módulo para importar os bots corretamente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from cs2_aimbot import CS2Aimbot
    from cs2_advanced_bot import CS2AdvancedBot
except ImportError:
    print("AVISO: Módulos do bot não encontrados, serão baixados se necessário.")

# Configuração básica
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_config.json')
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')

# Criar diretórios
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Configuração de log
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
        
        # Status do bot
        self.bot_status = 'inactive'
        self.current_xp = 0
        self.current_level = 0
        self.session_start_time = None
        
        logger.info(f"CS2 Client iniciado - Máquina: {self.machine_name}, VM ID: {self.vm_id}")
    
    def load_config(self):
        """Carregar ou criar arquivo de configuração"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    
                # Atualizar VM ID
                if self.vm_id and 'vm_id' in config:
                    config['vm_id'] = self.vm_id
                    
                return config
            except Exception as e:
                logger.error(f"Erro ao carregar arquivo de configuração: {e}")
        
        # Configuração padrão
        default_config = {
            'vm_id': self.vm_id,
            'server_url': self.server_url,
            'api_key': self.api_key,
            'steam_path': r'C:\Program Files (x86)\Steam\steam.exe',
            'cs2_app_id': 730,
            'bot_type': 'advanced',  # 'aimbot' ou 'advanced'
            'screenshot_interval': 300,  # segundos
            'max_session_time': 10800,  # 3 horas
            'auto_restart': True
        }
        
        # Salvar configuração
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config=None):
        """Salvar configuração no arquivo"""
        if config is None:
            config = self.config
            
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")
            return False
    
    def send_heartbeat(self):
        """Enviar notificação de status para o servidor"""
        current_time = time.time()
        
        # Verificar intervalo de envio do heartbeat
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
            
            logger.debug("Enviando heartbeat...")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                logger.debug(f"Heartbeat bem-sucedido: {response_data}")
                
                # Verificar se há novos trabalhos
                if response_data.get('has_jobs', False) and not self.active_job:
                    pending_jobs = response_data.get('pending_jobs', [])
                    if pending_jobs:
                        # Pegar o primeiro trabalho pendente
                        self.active_job = pending_jobs[0]
                        logger.info(f"Novo trabalho recebido: {self.active_job['id']} - Tipo: {self.active_job['type']}")
                        
                        # Iniciar trabalho
                        self.start_job(self.active_job)
            else:
                logger.error(f"Erro no heartbeat: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.error(f"Erro ao enviar heartbeat: {e}")
    
    def get_bot_config(self):
        """Obter configuração do bot do servidor"""
        try:
            url = f"{self.server_url}/api/v1/bot/config/{self.vm_id}"
            headers = {'Content-Type': 'application/json', 'X-API-Key': self.api_key}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                config = response.json()
                logger.info("Configuração do bot obtida")
                return config
            else:
                logger.error(f"Não foi possível obter configuração do bot: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao obter configuração do bot: {e}")
            return None
    
    def update_job_status(self, job_id, updates):
        """Atualizar status do trabalho no servidor"""
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
                logger.info(f"Status do trabalho atualizado: {job_id}")
                return True
            else:
                logger.error(f"Não foi possível atualizar status do trabalho: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao atualizar status do trabalho: {e}")
            return False
    
    def is_steam_running(self):
        """Verificar se o Steam está em execução"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'steam' in proc.info['name'].lower():
                    self.steam_process = proc
                    return True
            
            self.steam_process = None
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar status do Steam: {e}")
            return False
    
    def is_cs2_running(self):
        """Verificar se o CS2 está em execução"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                # Nome do processo CS2
                if 'cs2' in proc.info['name'].lower() or 'counter-strike' in proc.info['name'].lower():
                    self.cs2_process = proc
                    return True
            
            self.cs2_process = None
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar status do CS2: {e}")
            return False
    
    def start_steam(self):
        """Iniciar Steam"""
        if self.is_steam_running():
            logger.info("Steam já está em execução")
            return True
        
        try:
            steam_path = self.config.get('steam_path', r'C:\Program Files (x86)\Steam\steam.exe')
            logger.info(f"Iniciando Steam: {steam_path}")
            
            # Iniciar Steam
            subprocess.Popen([steam_path, "-silent"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            # Aguardar o Steam iniciar
            max_wait = 60  # saniye
            start_time = time.time()
            
            while not self.is_steam_running():
                if time.time() - start_time > max_wait:
                    logger.error("Não foi possível iniciar o Steam - tempo limite excedido")
                    return False
                
                logger.info("Iniciando Steam, aguardando...")
                time.sleep(5)
            
            logger.info("Steam iniciado com sucesso")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao iniciar Steam: {e}")
            return False
    
    def start_cs2(self):
        """Iniciar CS2 via Steam"""
        if self.is_cs2_running():
            logger.info("CS2 já está em execução")
            return True
        
        if not self.is_steam_running():
            if not self.start_steam():
                logger.error("Não foi possível iniciar CS2 - Steam não está em execução")
                return False
        
        try:
            # Iniciar CS2 via Steam
            cs2_app_id = self.config.get('cs2_app_id', 730)
            logger.info(f"Iniciando CS2 (AppID: {cs2_app_id})")
            
            # Iniciar CS2 com protocolo URL do Steam
            subprocess.Popen([f"steam://run/{cs2_app_id}"], shell=True)
            
            # Aguardar CS2 iniciar
            max_wait = 120  # saniye
            start_time = time.time()
            
            while not self.is_cs2_running():
                if time.time() - start_time > max_wait:
                    logger.error("Não foi possível iniciar CS2 - tempo limite excedido")
                    return False
                
                logger.info("Iniciando CS2, aguardando...")
                time.sleep(5)
            
            # Aguardar um pouco mais para o jogo carregar completamente
            logger.info("CS2 iniciado, aguardando o jogo carregar completamente...")
            time.sleep(30)
            
            # Trazer janela do CS2 para frente
            self.focus_cs2_window()
            
            logger.info("CS2 iniciado com sucesso")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao iniciar CS2: {e}")
            return False
    
    def focus_cs2_window(self):
        """Trazer janela do CS2 para frente"""
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
            logger.error(f"Erro ao focar janela do CS2: {e}")
    
    def take_screenshot(self):
        """Capturar e salvar captura de tela"""
        try:
            # Capturar screenshot
            monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
            screenshot = np.array(self.sct.grab(monitor))
            
            # Criar nome do arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(SCREENSHOTS_DIR, f"cs2_{timestamp}.jpg")
            
            # Salvar
            cv2.imwrite(filename, screenshot)
            logger.info(f"Captura de tela salva: {filename}")
            
            return filename
        except Exception as e:
            logger.error(f"Erro ao capturar tela: {e}")
            return None
    
    def init_bot(self, bot_config=None):
        """Iniciar instância do bot"""
        if bot_config is None:
            bot_config = self.get_bot_config()
            
        if bot_config is None:
            logger.error("Não foi possível obter configuração do bot, valores padrão serão usados")
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
            # Criar instância conforme tipo do bot
            bot_type = self.config.get('bot_type', 'advanced')
            
            if bot_type == 'aimbot':
                logger.info("Iniciando CS2Aimbot...")
                self.bot_instance = CS2Aimbot(model_path=bot_config.get('model_path'))
                
                # Atualizar parâmetros
                for key, value in bot_config.items():
                    if hasattr(self.bot_instance, key):
                        setattr(self.bot_instance, key, value)
            else:
                # Bot Avançado
                logger.info("Iniciando CS2AdvancedBot...")
                self.bot_instance = CS2AdvancedBot(config_file=None)
                
                # Definir parâmetros diretamente
                for key, value in bot_config.items():
                    if hasattr(self.bot_instance, key):
                        setattr(self.bot_instance, key, value)
            
            logger.info("Bot iniciado com sucesso")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao iniciar bot: {e}")
            return False
    
    def run_bot(self):
        """Executar o bot"""
        if self.bot_instance is None:
            if not self.init_bot():
                return False
        
        # Verificar se CS2 está em execução
        if not self.is_cs2_running():
            if not self.start_cs2():
                return False
        
        # Trazer janela do CS2 para frente
        self.focus_cs2_window()
        
        # Executar conforme tipo do bot
        try:
            if isinstance(self.bot_instance, CS2Aimbot):
                # Executar em modo Aimbot
                logger.info("Executando CS2Aimbot...")
                
                # Loop de captura de tela
                while self.running and self.is_cs2_running():
                    monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
                    frame = np.array(self.sct.grab(monitor))
                    
                    # Operações do bot
                    self.bot_instance.aim_at_target(frame)
                    
                    # Pequena espera
                    time.sleep(0.01)
            
            elif isinstance(self.bot_instance, CS2AdvancedBot):
                # Executar em modo Bot Avançado
                logger.info("Executando CS2AdvancedBot...")
                
                # Executar diretamente com método start
                self.bot_instance.running = True
                self.bot_instance.scanning = True
                self.bot_instance.start_time = time.time()
                
                # Loop do bot
                while self.running and self.is_cs2_running():
                    try:
                        # Verificar tecla de parada
                        if win32api.GetAsyncKeyState(win32con.VK_F8) & 0x8000:
                            logger.info("Parado com tecla F8")
                            break
                        
                        # Verificar tecla de pausa
                        if win32api.GetAsyncKeyState(win32con.VK_F7) & 0x8000:
                            self.bot_instance.paused = not self.bot_instance.paused
                            logger.info(f"Bot {'pausado' if self.bot_instance.paused else 'continuando'}")
                            time.sleep(0.5)  # Evitar múltiplos pressionamentos
                        
                        # Pular se o bot estiver pausado
                        if self.bot_instance.paused:
                            time.sleep(0.1)
                            continue
                        
                        # Lógica principal do bot
                        self.bot_instance.detect_and_aim()
                        
                        # Controle de varredura
                        if self.bot_instance.scanning:
                            self.bot_instance.scan_for_enemies()
                        
                        # Controlar uso de CPU
                        time.sleep(0.01)
                        
                    except Exception as e:
                        logger.error(f"Erro ao executar bot: {e}")
                        time.sleep(0.1)
                
                # Atualizar estatísticas
                self.current_xp = self.bot_instance.session_xp
                self.current_level = 0  # Obter nível do bot
            
            else:
                logger.error("Tipo de bot não suportado")
                return False
            
            logger.info("Execução do bot concluída")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao executar bot: {e}")
            return False
    
    def start_job(self, job):
        """Iniciar um trabalho específico"""
        if job['type'] == 'xp_farm':
            return self.start_xp_farm_job(job)
        elif job['type'] == 'drop_screenshot':
            return self.start_screenshot_job(job)
        elif job['type'] == 'claim_drop':
            return self.start_claim_drop_job(job)
        else:
            logger.error(f"Tipo de trabalho não suportado: {job['type']}")
            return False
    
    def start_xp_farm_job(self, job):
        """XP farm işini başlat"""
        logger.info(f"XP Farm işi başlatılıyor: {job['id']}")
        
        # Atualizar status do trabalho
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
            
            # Comunicar com o servidor
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
        
        # Parar o bot
        self.running = False
        self.bot_status = 'inactive'
        
        # Marcar trabalho como concluído
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
        
        # Atualizar status do trabalho
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
        
        # Trazer janela do CS2 para frente
        self.focus_cs2_window()
        
        # 5 saniye bekle
        time.sleep(5)
        
        # Ekran görüntüsü al
        screenshot_path = self.take_screenshot()
        
        if screenshot_path:
            # Marcar trabalho como concluído
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
        """Iniciar trabalho de solicitação de drop"""
        logger.info(f"Iniciando trabalho de solicitação de drop: {job['id']}")
        
        # Atualizar status do trabalho
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
        
        # Trazer janela do CS2 para frente
        self.focus_cs2_window()
        
        try:
            # Operações para acessar menu de drops
            # Nota: Esta parte deve ser personalizada conforme a interface do CS2
            
            # Clicar no menu do inventário
            pyautogui.click(x=600, y=50)
            time.sleep(2)
            
            # Clicar na aba de drops
            pyautogui.click(x=800, y=150)
            time.sleep(2)
            
            # Clicar no botão de resgatar
            pyautogui.click(x=700, y=500)
            time.sleep(3)
            
            # Capturar screenshot
            screenshot_path = self.take_screenshot()
            
            # Marcar trabalho como concluído
            self.update_job_status(job['id'], {
                'status': 'completed',
                'completion_time': datetime.now().isoformat(),
                'result': {
                    'screenshot_path': screenshot_path,
                    'claimed': True
                }
            })
            
            logger.info(f"Trabalho de solicitação de drop concluído: {job['id']}")
            
            # Aktif işi temizle
            self.active_job = None
            return True
            
        except Exception as e:
            logger.error(f"Erro ao solicitar drop: {e}")
            
            # İşi başarısız olarak işaretle
            self.update_job_status(job['id'], {
                'status': 'failed',
                'completion_time': datetime.now().isoformat(),
                'result': {
                    'error': f'Erro ao solicitar drop: {str(e)}'
                }
            })
            
            # Aktif işi temizle
            self.active_job = None
            return False
    
    def run(self):
        """Executar loop principal do cliente"""
        logger.info("Iniciando CS2 Client...")
        
        try:
            while True:
                # Verificar status do Steam e CS2
                self.is_steam_running()
                self.is_cs2_running()
                
                # Comunicar com o servidor
                self.send_heartbeat()
                
                # Se não há trabalho ativo e CS2 não está em execução, aguardar
                if not self.active_job and not self.cs2_process:
                    time.sleep(10)
                    continue
                
                # Se há trabalho ativo e CS2 não está em execução, iniciar CS2
                if self.active_job and not self.cs2_process:
                    if not self.start_cs2():
                        logger.error("Não foi possível iniciar CS2, trabalho em espera")
                        time.sleep(30)
                        continue
                
                # Aguardar 10 segundos
                time.sleep(10)
        
        except KeyboardInterrupt:
            logger.info("Interrompido pelo usuário")
        
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
        
        finally:
            logger.info("Encerrando CS2 Client...")
            
            # Se há trabalho ativo, finalizar
            if self.active_job:
                self.update_job_status(self.active_job['id'], {
                    'status': 'interrupted',
                    'completion_time': datetime.now().isoformat(),
                    'result': {
                        'error': 'Cliente encerrado'
                    }
                })
            
            # Parar o bot
            self.running = False
            self.bot_status = 'inactive'
            
            # Limpar recurso mss
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