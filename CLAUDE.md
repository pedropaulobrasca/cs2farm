# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a CS2 (Counter-Strike 2) bot farming system with three main components:

1. **Web Control Panel** (`web_control.py`) - Flask-based web interface for managing VMs and bot jobs
2. **VM Client** (`client.py`) - Runs on individual VMs, communicates with web panel and executes bot tasks  
3. **Bot Engines** (`cs2_aimbot.py`, `cs2_advanced_bot.py`, `cs2_farm_bot.py`) - YOLOv8-based target detection and game automation

## Development Setup

### Ambiente de Desenvolvimento WSL + Windows

Este projeto suporta desenvolvimento híbrido onde:
- **Claude Code** funciona no WSL (Linux) para desenvolvimento
- **Aplicação completa** roda no Windows nativo para teste com Hyper-V

#### Configuração no WSL (Desenvolvimento)
```bash
# No WSL - para usar Claude Code
cd /home/peter/projetos/cs2farm
python3 -m venv venv
source venv/bin/activate
pip install Flask flask-login werkzeug psutil requests
python web_control.py  # Modo desenvolvimento (simula VMs do Hyper-V)
# Acesso: http://localhost:8000 (admin/admin)
```

#### Sincronização para Windows (Testes)
```bash
# No WSL - sincronizar arquivos para Windows
./sync_to_windows.sh
```

```powershell
# No Windows PowerShell (executar como ADMINISTRADOR!)
cd C:\Users\Peter\Projetos\cs2farm
python -m venv venv_windows
venv_windows\Scripts\activate
pip install -r requirements_windows.txt
python web_control.py  # Modo produção (VMs reais do Hyper-V)
```

### Fluxo de Desenvolvimento
1. **Desenvolver no WSL** com Claude Code
2. **Sincronizar** com `./sync_to_windows.sh`  
3. **Testar no Windows** como Administrador para Hyper-V
4. **Repetir** conforme necessário

### Bot Development  
```bash
# Install bot dependencies (apenas Windows)
pip install ultralytics opencv-python numpy pyautogui keyboard mss torch pywin32 requests psutil

# Test individual bots
python cs2_aimbot.py
python cs2_advanced_bot.py
python cs2_farm_bot.py

# Test client VM communication
python client.py --server http://localhost:8000 --api-key SUA_CHAVE_API
```

### Virtual Environment
The project uses a Python virtual environment located in `venv/`. Always activate before development:
```bash
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

## Architecture

### Web Panel (`web_control.py`)
- Flask app with Bootstrap UI templates
- JSON file-based storage in `data/` directory
- User management with flask-login
- VM management (Hyper-V integration)
- Job queue system for bot tasks
- API endpoints for VM clients

### VM Client (`client.py`) 
- Heartbeat system with web panel
- Automatic Steam/CS2 game launching
- Bot execution and monitoring
- Screenshot capture and file uploads
- Session statistics tracking

### Bot Engines
- **cs2_aimbot.py**: YOLOv8 target detection with direct input emulation
- **cs2_advanced_bot.py**: Enhanced bot with movement prediction and recoil control
- **cs2_farm_bot.py**: Basic XP farming focused bot

### Configuration
- `bot_config.json`: Bot parameters (aim speed, FOV, thresholds, hotkeys)
- Templates in `templates/`: Bootstrap-based web UI (all in Portuguese)
- Model files expected in `runs/detect/cs2_model2/weights/best.pt`

## Key Files

- `web_control.py`: Main Flask application (21.8KB)
- `client.py`: VM client communication (30.2KB) 
- `cs2_aimbot.py`: Advanced aimbot with YOLOv8 (29.8KB)
- `cs2_advanced_bot.py`: Enhanced bot features (18.1KB)
- `requirements.txt`: Python dependencies
- `bot_config.json`: Bot configuration parameters
- `templates/`: Web UI templates (Portuguese)
- `data/`: JSON databases for users, VMs, jobs, configs

## Important Notes

- All code comments and UI text are in Portuguese Brazilian (pt-BR)
- Bot imports are temporarily commented out in web_control.py due to missing cv2 dependencies
- System designed for Windows VMs with CS2 game
- Uses direct input emulation to avoid affecting user's mouse cursor
- YOLOv8 model training required for optimal target detection
- Web panel runs on port 8000 by default

### WSL Compatibility Features
- Automatic WSL environment detection (`platform.system() == 'Linux' and 'microsoft' in platform.release().lower()`)
- VM operations simulated in WSL development mode
- Script `sync_to_windows.sh` for easy project synchronization
- Separate requirements files for WSL (`requirements.txt`) and Windows (`requirements_windows.txt`)
- Enhanced error messages for permission issues when running without Administrator privileges

## Development Patterns

- JSON file-based persistence (no database required)
- RESTful API design for VM communication  
- Bootstrap UI components with responsive design
- Logging to both console and files
- Error handling with user-friendly Portuguese messages
- Virtual environment isolation for dependencies