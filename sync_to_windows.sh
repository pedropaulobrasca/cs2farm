#!/bin/bash
# Script para sincronizar projeto WSL -> Windows

WINDOWS_PATH="/mnt/c/Users/Peter/Projetos/cs2farm"

echo "Sincronizando projeto para Windows..."

# Criar diretório no Windows se não existir
mkdir -p "$WINDOWS_PATH"

# Sincronizar arquivos (excluindo venv do WSL)
rsync -av --exclude='venv/' --exclude='__pycache__/' --exclude='*.pyc' . "$WINDOWS_PATH/"

echo "Projeto sincronizado para C:\Users\Peter\Projetos\cs2farm"
echo ""
echo "Para rodar no Windows:"
echo "1. Clique com botão direito no PowerShell -> 'Executar como administrador'"
echo "2. cd C:\Users\Peter\Projetos\cs2farm"  
echo "3. python -m venv venv_windows"
echo "4. venv_windows\Scripts\activate"
echo "5. pip install -r requirements_windows.txt"
echo "6. python web_control.py"
echo ""
echo "IMPORTANTE: PowerShell deve ser executado como ADMINISTRADOR para gerenciar VMs do Hyper-V!"