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

# Controle de mouse de baixo nível similar ao DirectInput para Windows
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
        """Envia entrada de mouse diretamente para o jogo, sem afetar o cursor normal"""
        # Flag extra do mouse_event: 0x0001 = MOUSEEVENTF_ABSOLUTE
        # Não move o cursor do usuário, apenas envia entradas para o jogo
        
        try:
            # Encontrar a janela do CS2
            hwnd = InputEmulator.get_cs2_window()
            if hwnd == 0:
                print("Janela do CS2 não encontrada!")
                return False
            
            # Obter dimensões da tela para coordenadas absolutas
            user32 = ctypes.windll.user32
            user32.SendMessageW(hwnd, win32con.WM_MOUSEMOVE, 0, win32api.MAKELONG(int(dx), int(dy)))
            
            # Enviar entrada do botão do mouse
            if button == "left":
                # Pressionar e soltar botão esquerdo do mouse
                user32.SendMessageW(hwnd, win32con.WM_LBUTTONDOWN, 0, 0)
                time.sleep(0.05)
                user32.SendMessageW(hwnd, win32con.WM_LBUTTONUP, 0, 0)
            
            return True
        except Exception as e:
            print(f"Não foi possível enviar entrada do mouse: {e}")
            return False

class CS2Aimbot:
    def __init__(self, model_path=r"runs\detect\cs2_model2\weights\best.pt"):
        self.model_path = model_path
        self.model = None
        self.confidence_threshold = 0.25  # Menor para mais detecções
        self.iou_threshold = 0.45

        # Configurações de mira (ajustadas para alta precisão)
        self.aim_smoothness = 2.0       # Pelo menos 2.0 para evitar divisão por zero
        self.aim_speed = 0.8            # Velocidade menor para evitar movimentos bruscos
        self.headshot_offset = -10      # Ajustado para melhores headshots
        self.target_lock_threshold = 15  # Limite mais tolerante
        self.aim_delay = 0.001          # Quase sem atraso
        
        # Shooting control
        self.auto_shoot = True          # Habilitar disparo automático
        self.shoot_delay = 0.1          # Atraso entre os disparos

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
        self.current_weapon = "ak47"    # Padrão de arma padrão
        self.shots_fired = 0
        self.last_shot_time = 0
        self.recoil_control_active = True
        self.recoil_recovery_time = 0.5  # Tempo após o qual o padrão de recuo é resetado

        # Configurações de rajada
        self.burst_fire_enabled = True
        self.burst_size = 4         # Tiros por rajada
        self.burst_delay = 0.25     # Segundos entre rajadas
        self.tap_fire_distance = 0.65  # Limite de distância para tiro único (0.0-1.0, porcentagem da tela)
        
        # Melhorias na seleção de alvo
        self.priority_zones = {
            "head": 1.0,            # Multiplicador de prioridade da cabeça
            "upper_body": 0.8,      # Multiplicador de prioridade do tronco superior
            "center_screen": 0.7,   # Fator de prioridade do centro da tela
            "distance": 0.5,        # Fator de distância (alvos mais próximos priorizados)
            "movement": 0.3         # Redução de prioridade para alvos em movimento
        }
        
        # Configurações de rastreamento de alvo
        self.target_memory = []     # Lembrar alvos recentes para rastreamento
        self.memory_duration = 0.5  # Por quanto tempo lembrar dos alvos (segundos)
        self.movement_prediction = True  # Habilitar predição de movimento para alvos em movimento
        self.prediction_factor = 0.2     # Quanto prever o movimento (0.0-1.0)
        
        # Otimizações de desempenho
        self.using_tensorrt = False  # Status da otimização TensorRT
        
        # Inicializar modelo com otimizações
        self.load_model()
        
    def load_model(self):
        """Carregar modelo YOLOv8 com otimizações para inferência em tempo real"""
        try:
            # Começar com modelo padrão
            self.model = YOLO(self.model_path)
            
            # Tentar otimizar com TensorRT se disponível
            try:
                import tensorrt
                # Exportar apenas uma vez, depois carregar o modelo otimizado
                engine_path = self.model_path.replace('.pt', '_tensorrt.engine')
                if not os.path.exists(engine_path):
                    self.model.export(format='engine', imgsz=640, half=True)
                self.model = YOLO(engine_path)
                self.using_tensorrt = True
                print(f"Otimização TensorRT habilitada para inferência mais rápida")
            except (ImportError, Exception) as e:
                # Voltar ao PyTorch padrão se TensorRT falhar
                print(f"Otimização TensorRT não disponível: {e}")
                # Usar meia precisão para melhor desempenho
                self.model.to(torch.device('cuda' if torch.cuda.is_available() else 'cpu'))
                if torch.cuda.is_available():
                    self.model.model.half()  # Usar FP16 se GPU disponível
                    
            print(f"Modelo carregado com sucesso: {self.model_path}")
        except Exception as e:
            print(f"Erro ao carregar modelo: {e}")
            self.model = None
    
    def preprocess_frame(self, frame):
        """Pré-processar frame para detecção otimizada"""
        # Aplicar melhoria de contraste para tornar alvos mais visíveis
        # Cria uma detecção mais robusta em diferentes condições de iluminação
        alpha = 1.1  # Controle de contraste (1.0 significa sem mudança)
        beta = 5     # Controle de brilho (0 significa sem mudança)
        
        # Aplicar ajuste de brilho/contraste
        adjusted = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        
        # Converter para RGB para YOLOv8
        if frame.shape[2] == 4:  # Formato BGRA
            frame_rgb = cv2.cvtColor(adjusted, cv2.COLOR_BGRA2RGB)
        else:  # Formato BGR
            frame_rgb = cv2.cvtColor(adjusted, cv2.COLOR_BGR2RGB)
            
        return frame_rgb
    
    def detect_targets(self, frame):
        """Detectar jogadores no frame usando YOLOv8"""
        if self.model is None:
            return []
            
        # Pré-processar o frame
        processed_frame = self.preprocess_frame(frame)
        
        # Executar inferência YOLOv8 com configurações otimizadas
        results = self.model(
            processed_frame, 
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            max_det=10,  # Limitar detecções para processamento mais rápido
            verbose=False
        )[0]
        
        # Extrair e retornar dados de detecção
        if len(results.boxes) > 0:
            return [{
                "xyxy": box.xyxy[0].cpu().numpy(),  # Converter para array numpy
                "confidence": box.conf[0].item(),
                "class_id": int(box.cls[0].item()),
                "x1y1x2y2": [float(x) for x in box.xyxy[0].tolist()]
            } for box in results.boxes]
        else:
            return []
    
    def select_best_target(self, targets, frame_width, frame_height, frame=None):
        """Selecionar o melhor alvo usando múltiplos critérios para precisão otimizada"""
        if not targets:
            return None
            
        # Coordenadas do centro da tela
        center_x, center_y = frame_width // 2, frame_height // 2
        
        # Sistema de pontuação aprimorado para seleção de alvo
        scored_targets = []
        current_time = time.time()
        
        # Fortalecer detecção de alvo no CS2
        print(f"Detectados {len(targets)} alvos potenciais")
        
        for i, target in enumerate(targets):
            x1, y1, x2, y2 = target["xyxy"]
            confidence = target["confidence"]
            
            # Debug imprimir cada alvo
            print(f"Alvo {i}: conf={confidence:.2f}, pos=({int(x1)},{int(y1)})→({int(x2)},{int(y2)})")
            
            # Cálculo preciso do centro da caixa
            box_width = x2 - x1
            box_height = y2 - y1
            center_box_x = x1 + (box_width / 2)
            center_box_y = y1 + (box_height / 2)
            
            # Estimativa da posição da cabeça (1/5 superior da caixa para modelos CS2)
            head_pos_y = y1 + (box_height * 0.18)  # 18% do topo, melhor para CS2
            
            # Cálculo de distância
            dx_center = center_box_x - center_x
            dy_center = center_box_y - center_y
            distance_center = math.sqrt(dx_center**2 + dy_center**2)
            
            # Distância da mira até a cabeça
            dx_head = center_box_x - center_x
            dy_head = head_pos_y - center_y
            distance_head = math.sqrt(dx_head**2 + dy_head**2)
            
            # Normalizar distâncias como porcentagem das dimensões da tela
            normalized_dist = distance_center / math.sqrt(frame_width**2 + frame_height**2)
            
            # Cálculo de tamanho (alvos maiores são mais próximos e fáceis de acertar)
            box_size = box_width * box_height
            normalized_size = box_size / (frame_width * frame_height)
            
            # CS2: Quanto mais próximo do centro, maior a prioridade
            center_bonus = 1.0 - (normalized_dist * 2)  # Bônus de proximidade do centro
            
            # Detecção de movimento (se rastreamento estiver habilitado)
            movement_penalty = 0
            if self.target_memory and frame is not None:
                # Verificar se este alvo coincide com algum anterior
                for old_target in self.target_memory:
                    if current_time - old_target["time"] > self.memory_duration:
                        continue  # Pular alvos expirados
                        
                    old_x1, old_y1, old_x2, old_y2 = old_target["xyxy"]
                    old_center_x = old_x1 + ((old_x2 - old_x1) / 2)
                    old_center_y = old_y1 + ((old_y2 - old_y1) / 2)
                    
                    # Verificar se é o mesmo alvo (por sobreposição de posição)
                    if (abs(center_box_x - old_center_x) < box_width * 0.5 and 
                        abs(center_box_y - old_center_y) < box_height * 0.5):
                        
                        # Calcular velocidade de movimento
                        movement_x = center_box_x - old_center_x
                        movement_y = center_box_y - old_center_y
                        movement_speed = math.sqrt(movement_x**2 + movement_y**2)
                        
                        # Aplicar penalidade de movimento a alvos em movimento rápido
                        movement_penalty = movement_speed * self.priority_zones["movement"]
                        break
            
            # Calcular pontuação de prioridade (menor é melhor) - otimizado para CS2
            # Equilibrar múltiplos fatores para seleção ótima de alvo
            priority_score = (
                distance_head * 0.4 -                           # Distância da cabeça (fator primário)
                normalized_size * 120 +                         # Bônus de tamanho (alvos maiores melhores)
                normalized_dist * 80 +                          # Penalidade de distância
                (1.0 - confidence) * 50 +                       # Penalidade de baixa confiança
                movement_penalty -                              # Penalidade de alvo em movimento
                center_bonus * 50                               # Bônus do centro da tela
            )
            
            # Armazenar alvo pontuado
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
            
        # Ordenar alvos por pontuação de prioridade (menor é melhor)
        scored_targets.sort(key=lambda t: t["priority"])
        
        if scored_targets:
            best = scored_targets[0]
            print(f"Melhor alvo: {best['index']} com prioridade {best['priority']:.2f}")
            print(f"Distância da mira: {best['distance']:.2f} pixels")
        
        # Atualizar memória de alvo para rastreamento
        if scored_targets and self.movement_prediction:
            best_target = scored_targets[0]
            self.target_memory.append({
                "xyxy": best_target["target"]["xyxy"],
                "time": current_time
            })
            
            # Remover alvos antigos da memória
            self.target_memory = [t for t in self.target_memory 
                                if current_time - t["time"] <= self.memory_duration]
        
        return scored_targets[0] if scored_targets else None
        
    def calculate_aim_point(self, target, frame_width, frame_height):
        """Calcular ponto de mira preciso com ajuste de headshot e predição"""
        # Cálculos básicos
        center_x = target["center_x"]
        head_y = target["head_y"]
        
        # Aplicar offset de headshot (mirar na cabeça)
        adjusted_y = head_y + self.headshot_offset
        
        # Aplicar predição de movimento se habilitado
        if self.movement_prediction and len(self.target_memory) >= 2:
            # Obter tempo atual para cálculos
            current_time = time.time()
            
            # Obter as duas posições mais recentes deste alvo
            recent_positions = sorted(
                [t for t in self.target_memory if current_time - t["time"] <= self.memory_duration],
                key=lambda t: t["time"], 
                reverse=True
            )
            
            if len(recent_positions) >= 2:
                # Calcular vetor de movimento
                current = recent_positions[0]
                previous = recent_positions[1]
                
                # Extrair centros
                current_x = current["xyxy"][0] + (current["xyxy"][2] - current["xyxy"][0]) / 2
                current_y = current["xyxy"][1] + (current["xyxy"][3] - current["xyxy"][1]) / 2
                previous_x = previous["xyxy"][0] + (previous["xyxy"][2] - previous["xyxy"][0]) / 2
                previous_y = previous["xyxy"][1] + (previous["xyxy"][3] - previous["xyxy"][1]) / 2
                
                # Calcular velocidade
                time_diff = current["time"] - previous["time"]
                if time_diff > 0:
                    velocity_x = (current_x - previous_x) / time_diff
                    velocity_y = (current_y - previous_y) / time_diff
                    
                    # Prever posição futura (predição linear básica)
                    prediction_time = 0.1  # Predição de 100ms
                    center_x += velocity_x * prediction_time * self.prediction_factor
                    adjusted_y += velocity_y * prediction_time * self.prediction_factor
        
        # Calcular delta do centro da tela (onde está a mira)
        delta_x = center_x - (frame_width // 2)
        delta_y = adjusted_y - (frame_height // 2)
        
        return delta_x, delta_y
        
    def mouse_move(self, dx, dy):
        """Enviar comando de movimento do mouse diretamente para CS2, sem afetar o cursor do usuário"""
        if self.aim_smoothness <= 1.0:
            # Movimento direto simples
            move_x = int(dx * self.aim_speed)
            move_y = int(dy * self.aim_speed)
            InputEmulator.send_mouse_input_to_game(move_x, move_y)
            return
            
        # Movimento suave e adaptativo semelhante ao humano
        steps = int(self.aim_smoothness)
        # Prevenir erro de divisão por zero
        if steps <= 1:
            steps = 2  # Pelo menos 2 passos
        
        # Movimento semelhante à curva de Bezier - mais natural que linear
        # Acelera, depois desacelera para padrão de movimento humano
        for i in range(steps):
            # Fator de interpolação de Bezier (acelerar depois desacelerar)
            t = i / (steps - 1)
            bezier_factor = 4 * t * (1 - t)  # Equivalente a uma curva de Bezier quadrática
            
            # Aplicar curva de Bezier ao movimento (mais rápido no meio, mais lento no início/fim)
            move_factor = bezier_factor * self.aim_speed
            
            # Calcular tamanho do passo com fator de Bezier
            step_x = int((dx / steps) * move_factor)
            step_y = int((dy / steps) * move_factor)
            
            # Pular movimentos muito pequenos (0 pixels)
            if abs(step_x) < 1 and abs(step_y) < 1:
                continue
                
            # Variar cada passo ligeiramente para movimento mais humano
            rand_factor = 0.05  # 5% de aleatoriedade
            rand_x = int(step_x * (1 + (np.random.random() - 0.5) * rand_factor))
            rand_y = int(step_y * (1 + (np.random.random() - 0.5) * rand_factor))
            
            # Aplicar movimento do mouse diretamente ao jogo
            InputEmulator.send_mouse_input_to_game(rand_x, rand_y)
            
            # Tempo de espera adaptativo (ligeiramente aleatorizado para movimento natural)
            sleep_time = 0.001 * (1 + (np.random.random() - 0.5) * 0.3)
            time.sleep(sleep_time)
    
    def mouse_click(self):
        """Simular clique do mouse com tempo e comportamento humanos"""
        now = time.time()
        self.shots_fired += 1
        self.last_shot_time = now
        
        # Tempos realistas de pressionar e soltar
        press_time = 0.02 + (np.random.random() * 0.03)  # Tempo de pressão 20-50ms
        
        # Atirar diretamente no jogo
        InputEmulator.send_mouse_input_to_game(0, 0, "left")
    
    def apply_recoil_control(self):
        """Aplicar compensação de recuo baseada no padrão da arma e tiros disparados"""
        if not self.recoil_control_active or self.shots_fired == 0:
            return
            
        # Resetar contador de recuo se não atirarmos por um tempo
        now = time.time()
        if now - self.last_shot_time > self.recoil_recovery_time:
            self.shots_fired = 0
            return
            
        # Obter padrão de recuo correto para arma atual
        pattern = self.recoil_patterns.get(self.current_weapon, self.recoil_patterns["ak47"])
        
        # Aplicar compensação de recuo correspondente se dentro do alcance do padrão
        if self.shots_fired <= len(pattern):
            # Obter vetor de recuo para tiro atual
            recoil_x, recoil_y = pattern[self.shots_fired - 1]
            
            # Aplicar compensação (negativo do recuo)
            InputEmulator.send_mouse_input_to_game(recoil_x, recoil_y)
    
    def should_fire(self, target, frame_width, frame_height):
        """Determinar se devemos atirar baseado em múltiplos fatores táticos"""
        # Nunca atirar se não houver alvo
        if not target:
            return False
            
        # Verificar se a mira é precisa o suficiente - mais tolerante
        precise_aim = (abs(target["dx_head"]) < self.target_lock_threshold * 1.5 and 
                      abs(target["dy_head"]) < self.target_lock_threshold * 1.5)
        
        # Se rajada estiver habilitada, aplicar lógica de rajada
        if self.burst_fire_enabled:
            now = time.time()
            
            # Verificar se alvo está longe (usar distância normalizada)
            is_distant_target = target["normalized_dist"] > self.tap_fire_distance
            
            if is_distant_target:
                # Para alvos distantes, usar tiro único (mais preciso)
                if now - self.last_shot_time < 0.25:  # Mais rápido (era 0.4)
                    return False
            else:
                # Para alvos próximos, usar rajada
                if self.shots_fired >= self.burst_size:
                    # Esperar atraso da rajada antes de atirar novamente
                    if now - self.last_shot_time < self.burst_delay * 0.7:  # Mais rápido
                        return False
                    else:
                        # Resetar contador de rajada após atraso
                        self.shots_fired = 0
        
        # Retornar decisão final
        return precise_aim
    
    def aim_at_target(self, frame, return_annotated=False):
        """Função principal para detectar, mirar e atirar em alvos"""
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
            print(f"Mirando: Movendo mouse por dx={delta_x}, dy={delta_y}")
            
            # Movimento de mira suave para movimento humano
            if abs(delta_x) > 1 or abs(delta_y) > 1:  # Mover apenas se distância significativa
                try:
                    # Mais confiável para controle direto do mouse
                    self.mouse_move(delta_x, delta_y)
                    print(f"Mouse movido por: {delta_x}, {delta_y}")
                    
                    # Pequeno atraso para mira se acomodar
                    time.sleep(self.aim_delay)
                except Exception as e:
                    print(f"Erro de movimento do mouse: {e}")
            
            # Decide whether to shoot
            should_shoot = self.should_fire(best_target, frame_width, frame_height)
            if should_shoot and self.auto_shoot:
                print("ATIRANDO!")
                try:
                    # Atirar no alvo
                    self.mouse_click()
                    print("Tiro disparado")
                    
                    # Apply recoil control after shooting
                    if self.recoil_control_active:
                        self.apply_recoil_control()
                except Exception as e:
                    print(f"Erro de clique do mouse: {e}")
        
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

# Exemplo de uso se executado como standalone
if __name__ == "__main__":
    print("CS2 Aimbot v2.0 - Edição DirectInput")
    print("======================================")
    print("F1: Alternar Aimbot (Iniciar/Parar)")
    print("F2: Alternar Disparo Automático")
    print("F3: Aumentar Sensibilidade")
    print("F4: Diminuir Sensibilidade")
    print("F5: Alternar Visualização de Debug")
    print("F6: Alternar Modo DirectInput (Direto para Jogo)")
    print("Ctrl+C: Sair do Programa")
    print("======================================")
    
    # Initialize aimbot
    aimbot = CS2Aimbot(model_path=r"runs\detect\cs2_model2\weights\best.pt")
    # Detectar mais objetos com limite de confiança baixo
    aimbot.confidence_threshold = 0.25
    
    # Configuração de captura de tela
    sct = mss.mss()
    monitor = {
        "top": 0, 
        "left": 0, 
        "width": 1920, 
        "height": 1080
    }
    
    # Variáveis de controle
    running = True
    aimbot_enabled = True
    debug_mode = True
    directinput_mode = True  # Modo de envio de entrada direta para o jogo
    
    # Loop principal
    try:
        print("Aimbot executando... Pressione Ctrl+C para parar")
        print("Aguardando janela do CS2...")
        
        while running:
            # Verificar janela do CS2
            cs2_hwnd = InputEmulator.get_cs2_window()
            if cs2_hwnd == 0:
                print("Janela do CS2 não encontrada! Inicie o CS2 e tente novamente.")
                time.sleep(3)
                continue
            else:
                print(f"Janela do CS2 encontrada (HWND: {cs2_hwnd})")
            
            # Verificar controles do teclado
            if keyboard.is_pressed('f1'):
                aimbot_enabled = not aimbot_enabled
                print(f"Aimbot {'habilitado' if aimbot_enabled else 'desabilitado'}")
                time.sleep(0.3)  # Prevenir múltiplas alternâncias
                
            if keyboard.is_pressed('f2'):
                aimbot.auto_shoot = not aimbot.auto_shoot
                print(f"Disparo automático {'habilitado' if aimbot.auto_shoot else 'desabilitado'}")
                time.sleep(0.3)
                
            if keyboard.is_pressed('f3'):
                aimbot.aim_speed += 0.1
                print(f"Sensibilidade aumentada para {aimbot.aim_speed:.1f}")
                time.sleep(0.2)
                
            if keyboard.is_pressed('f4'):
                aimbot.aim_speed = max(0.1, aimbot.aim_speed - 0.1)
                print(f"Sensibilidade diminuída para {aimbot.aim_speed:.1f}")
                time.sleep(0.2)
                
            if keyboard.is_pressed('f5'):
                debug_mode = not debug_mode
                print(f"Visualização de debug {'habilitada' if debug_mode else 'desabilitada'}")
                time.sleep(0.3)
            
            if keyboard.is_pressed('f6'):
                directinput_mode = not directinput_mode
                print(f"Modo DirectInput {'habilitado' if directinput_mode else 'desabilitado'}")
                time.sleep(0.3)
            
            # Capturar tela
            frame = np.array(sct.grab(monitor))
            
            # Processar frame se aimbot estiver habilitado
            if aimbot_enabled:
                result = aimbot.aim_at_target(frame, return_annotated=debug_mode)
                
                # Mostrar resultado para debug
                if debug_mode and result is not None:
                    cv2.imshow("CS2 Aimbot Debug", result)
            
            # Verificar tecla de saída
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            # Limitar taxa de processamento
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("Aimbot parado pelo usuário")
    
    finally:
        cv2.destroyAllWindows() 