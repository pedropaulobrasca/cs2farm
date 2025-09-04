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
        # Carregar configuração do arquivo se existir
        self.config_file = config_file
        self.load_config()
        
        # Propriedades da tela
        self.screen_width, self.screen_height = pyautogui.size()
        self.center_x, self.center_y = self.screen_width // 2, self.screen_height // 2
        
        # Variáveis de execução
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
        
        # Estatísticas
        self.kills = 0
        self.shots = 0
        self.hits = 0
        self.start_time = None
        self.session_xp = 0
        
        # Inicializar modelo YOLOv8
        self.load_model()
        
        # Configuração de captura de tela
        self.sct = mss.mss()
        self.update_monitor_region()
        
        # Monitoramento de desempenho
        self.fps = 0
        self.last_time = time.time()
        self.frame_count = 0
        
        # Criar diretório de logs
        os.makedirs("logs", exist_ok=True)
        self.log_file = f"logs/cs2bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        self.log("CS2 Bot Avançado inicializado")
        
    def load_config(self):
        """Carregar configuração do arquivo ou usar padrões"""
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
        
        # Tentar carregar do arquivo
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    
                # Atualizar config padrão com valores carregados
                for key, value in loaded_config.items():
                    default_config[key] = value
                    
                self.log(f"Configuração carregada de {self.config_file}")
        except Exception as e:
            self.log(f"Erro ao carregar config: {e}. Usando padrões.")
        
        # Definir atributos de configuração
        for key, value in default_config.items():
            setattr(self, key, value)
        
        # Salvar config de volta ao arquivo
        self.save_config()
        
    def save_config(self):
        """Salvar configuração atual no arquivo"""
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
            self.log(f"Erro ao salvar config: {e}")
    
    def update_monitor_region(self):
        """Atualizar a região da tela para capturar baseado nas configurações de FOV"""
        self.monitor = {
            "top": int(self.center_y - self.screen_height * self.fov_y / 200),
            "left": int(self.center_x - self.screen_width * self.fov_x / 200),
            "width": int(self.screen_width * self.fov_x / 100),
            "height": int(self.screen_height * self.fov_y / 100)
        }
    
    def load_model(self):
        """Carregar o modelo YOLOv8 para detecção de jogadores"""
        try:
            self.model = YOLO(self.model_path)
            self.log(f"Modelo carregado de {self.model_path}")
        except Exception as e:
            self.log(f"Erro ao carregar modelo: {e}")
            self.model = None
    
    def log(self, message):
        """Registrar uma mensagem no console e arquivo de log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + "\n")
        except:
            pass
    
    def mouse_move(self, dx, dy, smooth=True):
        """Mover mouse com suavização opcional para movimento mais natural"""
        if smooth and self.aim_smoothness > 1.0:
            # Dividir movimento em passos menores
            steps = int(self.aim_smoothness)
            step_x = dx / steps
            step_y = dy / steps
            
            for _ in range(steps):
                # Escalar por velocidade de mira
                move_x = int(step_x * self.aim_speed)
                move_y = int(step_y * self.aim_speed)
                
                if move_x != 0 or move_y != 0:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
                    time.sleep(0.001)  # Pequeno atraso entre movimentos
        else:
            # Movimento único escalado por velocidade de mira
            move_x = int(dx * self.aim_speed)
            move_y = int(dy * self.aim_speed)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
    
    def mouse_click(self):
        """Clicar no botão esquerdo do mouse para atirar"""
        now = time.time()
        self.shots += 1
        self.shots_fired += 1
        self.last_shot_time = now
        
        # Aplicar eventos de botão esquerdo pressionado/solto
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        
        # Aplicar controle de recuo se habilitado
        if self.recoil_control:
            self.apply_recoil_control()
    
    def apply_recoil_control(self):
        """Aplicar compensação de recuo baseada no tipo de arma e tiros disparados"""
        # Este é um padrão de recuo simplificado para rifles do CS2 (como AK-47)
        # Ajuste isto para diferentes armas ou baseado em testes do jogo
        
        if self.shots_fired <= 3:
            # Primeiros tiros - leve recuo para cima
            self.mouse_move(0, -3, smooth=False)
        elif self.shots_fired <= 10:
            # Tiros do meio - recuo mais forte para cima + lateral
            self.mouse_move(
                -2 if self.shots_fired % 2 == 0 else 2,  # Alternando esquerda-direita
                -4,  # Compensação para cima
                smooth=False
            )
        else:
            # Tiros posteriores - padrão complexo
            # Simplificado baseado em padrões comuns de spray de rifle
            angle = math.sin(self.shots_fired * 0.5) * 3
            self.mouse_move(int(angle), -5, smooth=False)
    
    def reload(self):
        """Simular pressionamento da tecla R para recarregar"""
        self.log("Recarregando arma")
        win32api.keybd_event(0x52, 0, 0, 0)  # R key down
        time.sleep(0.05)
        win32api.keybd_event(0x52, 0, win32con.KEYEVENTF_KEYUP, 0)  # R key up
        
        # Resetar contador de tiros
        self.shots_fired = 0
        time.sleep(0.1)  # Pequeno atraso após comando de recarregar
    
    def scan_for_enemies(self):
        """Rotacionar a câmera para procurar inimigos"""
        if not self.scanning:
            return
            
        # Calcular quantidade de rotação baseada em velocidade e tempo
        rotation_amount = self.rotation_speed * 5
        
        # Aplicar rotação baseada na direção
        self.mouse_move(rotation_amount * self.scan_direction, 0, smooth=False)
        
        # Atualizar ângulo de varredura
        self.scan_angle += rotation_amount * self.scan_direction
        
        # Mudar direção se rotacionamos demais
        if abs(self.scan_angle) > 170:
            self.scan_direction *= -1
            self.scan_angle = 170 * self.scan_direction
    
    def select_best_target(self, boxes, classes, confs):
        """Selecionar o melhor alvo baseado em critérios de prioridade"""
        if len(boxes) == 0:
            return None
            
        targets = []
        
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box.tolist()
            conf = confs[i]
            cls = int(classes[i])
            
            # Calcular centro da caixa delimitadora
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Calcular distância do centro da tela
            dx = center_x - self.monitor["width"] / 2
            dy = center_y - self.monitor["height"] / 2
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Calcular tamanho da caixa (alvos maiores estão mais próximos)
            size = (x2 - x1) * (y2 - y1)
            
            # Calcular pontuação de prioridade do alvo (menor é melhor)
            # Fatores: distância da mira, confiança, tamanho
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
        
        # Ordenar alvos por prioridade (menor é melhor)
        targets.sort(key=lambda t: t["priority"])
        
        # Retornar o melhor alvo
        return targets[0]
    
    def detect_and_aim(self):
        """Capturar tela, detectar jogadores e mirar no melhor alvo"""
        # Capturar tela
        img = np.array(self.sct.grab(self.monitor))
        
        # Converter para RGB para YOLOv8
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        
        # Executar inferência YOLOv8
        if self.model is not None:
            results = self.model(img_rgb, conf=self.confidence_threshold)[0]
            
            if len(results.boxes) > 0:
                # Obter dados de detecção
                boxes = results.boxes.xyxy
                classes = results.boxes.cls
                confs = results.boxes.conf
                
                # Selecionar melhor alvo
                target = self.select_best_target(boxes, classes, confs)
                
                if target:
                    # Parar varredura quando alvo encontrado
                    self.scanning = False
                    
                    # Calcular alvo de mira (com deslocamento de headshot)
                    target_x = target["dx"]
                    target_y = target["dy"] + self.headshot_offset
                    
                    # Mirar no alvo se está longe o suficiente do centro
                    if abs(target_x) > 3 or abs(target_y) > 3:
                        self.mouse_move(int(target_x), int(target_y))
                    
                    # Uma vez que a mira está no alvo
                    if abs(target_x) < 10 and abs(target_y) < 10:
                        # Verificar se devemos atirar
                        now = time.time()
                        should_shoot = True
                        
                        # Aplicar lógica de rajada se habilitada
                        if self.burst_fire:
                            if self.shots_fired >= self.burst_size:
                                # Aguardar atraso da rajada antes de atirar novamente
                                if now - self.last_shot_time < self.burst_delay:
                                    should_shoot = False
                                else:
                                    # Resetar contador de rajada após atraso
                                    self.shots_fired = 0
                        
                        # Atirar se condições forem atendidas
                        if should_shoot:
                            self.mouse_click()
                            self.hits += 1  # Assumindo acerto quando mirado corretamente
                            
                            # Verificar se precisamos recarregar
                            if self.auto_reload and self.shots_fired > self.reload_ammo_threshold:
                                self.reload()
                else:
                    # Resetar se não há alvo válido
                    self.scanning = True
                    self.shots_fired = 0
            else:
                # Nenhuma detecção, procurar inimigos
                self.scanning = True
                self.shots_fired = 0
        
        # Atualizar estatísticas de desempenho
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_time >= 1:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_time = current_time
            self.log(f"FPS: {self.fps}, Tiros: {self.shots}, Acertos: {self.hits}")
    
    def start(self):
        """Iniciar o bot"""
        self.log(f"Iniciando CS2 Bot Avançado - Pressione '{self.hotkeys['stop']}' para parar, '{self.hotkeys['pause']}' para pausar/continuar")
        
        self.running = True
        self.scanning = True
        self.start_time = time.time()
        
        while self.running:
            try:
                # Verificar tecla de parada
                if keyboard.is_pressed(self.hotkeys['stop']):
                    self.running = False
                    self.log("Bot parado pelo usuário")
                    break
                
                # Verificar tecla de pausa
                if keyboard.is_pressed(self.hotkeys['pause']):
                    self.paused = not self.paused
                    self.log(f"Bot {'pausado' if self.paused else 'continuando'} pelo usuário")
                    time.sleep(0.5)  # Prevenir múltiplos acionamentos
                
                # Pular processamento se pausado
                if self.paused:
                    time.sleep(0.1)
                    continue
                
                # Lógica principal do bot
                self.detect_and_aim()
                
                # Se não está mirando, procurar inimigos
                if self.scanning:
                    self.scan_for_enemies()
                
                # Pequeno atraso para controlar uso de CPU
                time.sleep(0.01)
                
            except Exception as e:
                self.log(f"Erro no loop principal: {e}")
                time.sleep(0.1)
        
        # Limpar e salvar estatísticas
        self.save_session_stats()
        cv2.destroyAllWindows()
    
    def save_session_stats(self):
        """Salvar estatísticas da sessão no arquivo"""
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
                self.log(f"Estatísticas da sessão salvas em {stats_file}")
                
                # Log resumo
                self.log(f"Resumo da sessão: Duração: {stats['duration_formatted']}, Tiros: {stats['shots']}, Acertos: {stats['hits']}, Precisão: {stats['accuracy']}%")
            except Exception as e:
                self.log(f"Erro ao salvar estatísticas: {e}")
    
    def run_in_thread(self):
        """Executar o bot em uma thread separada"""
        thread = threading.Thread(target=self.start)
        thread.daemon = True
        thread.start()
        return thread

if __name__ == "__main__":
    # Dar tempo para mudar para a janela do jogo
    print("Mude para a janela do CS2 em 5 segundos...")
    time.sleep(5)
    
    # Criar e iniciar o bot
    bot = CS2AdvancedBot()
    bot.start() 