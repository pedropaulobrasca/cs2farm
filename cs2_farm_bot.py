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
        # Configuração
        self.model_path = r"runs\detect\cs2_model2\weights\best.pt"
        self.confidence_threshold = 0.4
        self.running = False
        self.paused = False
        self.screen_width, self.screen_height = pyautogui.size()
        self.center_x, self.center_y = self.screen_width // 2, self.screen_height // 2
        
        # Configurações - ajuste baseado na sensibilidade do seu jogo
        self.rotation_speed = 1.0
        self.aim_speed = 0.5
        self.fov_x, self.fov_y = 70, 40  # Campo de visão de detecção (% da tela)
        self.headshot_offset = -10  # Deslocamento vertical para headshots (negativo = mais alto)
        
        # Controle de varredura
        self.scanning = False
        self.scan_direction = 1  # 1 para direita, -1 para esquerda
        self.scan_angle = 0
        
        # Inicializar o modelo YOLOv8
        self.load_model()
        
        # Configuração de captura de tela
        self.sct = mss.mss()
        self.monitor = {
            "top": int(self.center_y - self.screen_height * self.fov_y / 200),
            "left": int(self.center_x - self.screen_width * self.fov_x / 200),
            "width": int(self.screen_width * self.fov_x / 100),
            "height": int(self.screen_height * self.fov_y / 100)
        }
        
        # Monitoramento de desempenho
        self.fps = 0
        self.last_time = time.time()
        self.frame_count = 0
        
        print("CS2 Bot inicializado")
        
    def load_model(self):
        """Carregar o modelo YOLOv8 para detecção de jogadores"""
        try:
            self.model = YOLO(self.model_path)
            print(f"Modelo carregado de {self.model_path}")
        except Exception as e:
            print(f"Erro ao carregar modelo: {e}")
            self.model = None
        
    def mouse_move(self, dx, dy):
        """Mover o mouse pelo delta especificado com suavização"""
        # Escalar o movimento baseado na velocidade de mira
        dx = int(dx * self.aim_speed)
        dy = int(dy * self.aim_speed)
        
        # Aplicar o movimento
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)
    
    def mouse_click(self):
        """Clicar no botão esquerdo do mouse para atirar"""
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)  # Segurar por um curto tempo
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    def scan_for_enemies(self):
        """Rotacionar a câmera para procurar inimigos"""
        if not self.scanning:
            return
            
        # Calcular quantidade de rotação baseada em velocidade e tempo
        rotation_amount = self.rotation_speed * 5
        
        # Aplicar rotação baseada na direção
        self.mouse_move(rotation_amount * self.scan_direction, 0)
        
        # Atualizar ângulo de varredura
        self.scan_angle += rotation_amount * self.scan_direction
        
        # Mudar direção se rotacionamos demais
        if abs(self.scan_angle) > 170:
            self.scan_direction *= -1
            self.scan_angle = 170 * self.scan_direction
    
    def detect_and_aim(self):
        """Capturar tela, detectar jogadores e mirar no mais próximo"""
        # Capturar tela
        img = np.array(self.sct.grab(self.monitor))
        
        # Converter para RGB para YOLOv8
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        
        # Executar inferência YOLOv8
        if self.model is not None:
            results = self.model(img_rgb, conf=self.confidence_threshold)[0]
            
            # Parar varredura se encontramos inimigos
            if len(results.boxes) > 0:
                self.scanning = False
                
                # Encontrar o alvo mais próximo do centro
                closest_dist = float('inf')
                target_x, target_y = 0, 0
                
                for box in results.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # Calcular centro da caixa delimitadora
                    box_center_x = (x1 + x2) / 2
                    box_center_y = (y1 + y2) / 2
                    
                    # Calcular distância do centro da tela
                    dx = box_center_x - img_rgb.shape[1] / 2
                    dy = box_center_y - img_rgb.shape[0] / 2
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    if dist < closest_dist:
                        closest_dist = dist
                        target_x = dx
                        # Aplicar deslocamento de headshot - mirar mais alto no corpo
                        target_y = dy + self.headshot_offset
                
                # Converter coordenadas do alvo para coordenadas de tela
                screen_x = target_x
                screen_y = target_y
                
                # Mirar no alvo
                if abs(screen_x) > 5 or abs(screen_y) > 5:  # Só mover se distância significativa
                    self.mouse_move(int(screen_x), int(screen_y))
                    # Pequeno atraso para permitir estabilização da mira
                    time.sleep(0.05)
                
                # Se estamos muito perto do alvo, atirar
                if abs(screen_x) < 10 and abs(screen_y) < 10:
                    self.mouse_click()
                    time.sleep(0.1)  # Pequeno atraso após atirar
            else:
                # Se não encontrou inimigos, continuar varredura
                self.scanning = True
        
        # Calcular FPS
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_time >= 1:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_time = current_time
            print(f"FPS: {self.fps}")
        
        # Você pode desenhar na imagem para debug, ex.:
        # cv2.imshow("CS2Bot Vision", img_rgb)
        # cv2.waitKey(1)
    
    def start(self):
        """Iniciar o bot"""
        print("Iniciando CS2Bot - Pressione 'F8' para parar, 'F7' para pausar/continuar")
        self.running = True
        self.scanning = True
        
        while self.running:
            try:
                # Verificar tecla de parada
                if keyboard.is_pressed('f8'):
                    self.running = False
                    print("Bot parado")
                    break
                
                # Verificar tecla de pausa
                if keyboard.is_pressed('f7'):
                    self.paused = not self.paused
                    print(f"Bot {'pausado' if self.paused else 'continuando'}")
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
                print(f"Erro: {e}")
                time.sleep(0.1)
                
        # Limpar
        cv2.destroyAllWindows()
        
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
    bot = CS2Bot()
    bot.start() 