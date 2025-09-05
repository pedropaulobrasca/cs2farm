# Bot de Farm e Sistema de Gerenciamento CS2

Este projeto é um sistema que pode realizar farming de XP totalmente automático, solicitar drops e capturar telas no jogo CS2. Usando processamento de imagem baseado em YOLOv8, ele detecta inimigos, mira e atira com alta precisão.

## Recursos

- **Detecção de Objetos YOLOv8**: Detecção de jogadores usando seu modelo personalizado treinado
- **Operação Autônoma**: Rotação automática para buscar, mirar e atirar em inimigos sem entrada do usuário
- **Seleção Inteligente de Alvos**: Alvos priorizados com base em distância, tamanho e nível de confiança
- **Controle de Recuo**: Movimentos compensatórios do mouse para controlar o recuo da arma
- **Modo de Tiro em Rajada**: Tamanho de rajada e atraso configuráveis para padrões de tiro mais realistas
- **Parâmetros Ajustáveis**: Configure facilmente todos os parâmetros através do arquivo de configuração
- **Estatísticas da Sessão**: Rastreia o desempenho e registra logs detalhados
- **Operação AFK Completa**: Funciona completamente sem supervisão
- **Gerenciamento Baseado na Web**: Interface web para gerenciamento de múltiplas VMs
- **Integração com VM**: Integração com máquinas virtuais Hyper-V

## Componentes do Sistema

O projeto consiste em três componentes principais:

1. **Bot CS2 (cs2_aimbot.py e cs2_advanced_bot.py)**
   - Detecção de alvos baseada em YOLOv8
   - Mecanismos precisos de mira e disparo
   - Controle avançado de recuo de armas
   - Previsão de movimento e rastreamento

2. **Painel de Controle Web (web_control.py)**
   - Interface web baseada em Flask
   - Gerenciamento de VMs e bots
   - Gerenciamento de usuários e autenticação
   - Fila de trabalhos e monitoramento de status

3. **Cliente VM (client.py)**
   - Comunicação com o servidor
   - Execução local de trabalhos do bot
   - Inicialização automática do Steam e CS2
   - Estatísticas da sessão e capturas de tela

## Instalação

### Desenvolvimento WSL + Windows (Recomendado)

Este projeto suporta desenvolvimento híbrido para aproveitar o melhor dos dois ambientes:

#### WSL (Desenvolvimento com Claude Code)
```bash
# No WSL Ubuntu
cd /home/peter/projetos/cs2farm
python3 -m venv venv
source venv/bin/activate
pip install Flask flask-login werkzeug psutil requests
python web_control.py  # Modo desenvolvimento (simula VMs)
```
Acesse: `http://localhost:8000` (admin/admin)

#### Windows (Testes com Hyper-V Real)
```bash
# No WSL - sincronizar projeto
./sync_to_windows.sh
```

```powershell
# No Windows PowerShell (EXECUTAR COMO ADMINISTRADOR!)
cd C:\Users\Peter\Projetos\cs2farm
python -m venv venv_windows
venv_windows\Scripts\activate
pip install -r requirements_windows.txt
python web_control.py  # Modo produção (VMs reais)
```

⚠️ **IMPORTANTE**: PowerShell deve ser executado como **Administrador** para gerenciar VMs do Hyper-V!

### Servidor (Painel de Controle Web) - Instalação Tradicional

1. Instale as dependências:
```bash
pip install Flask flask-login werkzeug psutil requests
```

2. Inicie o servidor:
```bash
python web_control.py
```

3. Acesse `http://localhost:8000` no seu navegador e faça login com usuário/senha padrão (admin/admin)

### Cliente VM

1. Instale as dependências:
```bash
pip install ultralytics opencv-python numpy pyautogui keyboard mss torch pywin32 requests psutil
```

2. Coloque seu modelo YOLOv8 em `runs\detect\cs2_model2\weights\best.pt`.

3. Inicie o cliente:
```bash
python client.py --server http://localhost:8000 --api-key SUA_CHAVE_API
```

## Uso

### Pela Interface Web

1. Gerencie VMs (iniciar, parar, configurar)
2. Crie trabalhos do bot (farm de XP, captura de tela, solicitação de drop)
3. Monitore status e estatísticas dos trabalhos

### Configuração da VM

Você pode configurar as VMs editando o arquivo `bot_config.json` com as seguintes configurações:

- `model_path`: Caminho para seu modelo YOLOv8
- `confidence_threshold`: Nível mínimo de confiança para detecção de inimigos (0.0-1.0)
- `rotation_speed`: Velocidade de rotação durante a varredura
- `aim_speed`: Multiplicador de velocidade do movimento do mouse
- `fov_x`, `fov_y`: Campo de visão para detecção (porcentagem da tela)
- `headshot_offset`: Deslocamento vertical para tiros na cabeça (valores negativos miram mais alto)
- `aim_smoothness`: Valores mais altos para movimentos mais naturais e humanos
- `recoil_control`: Ativar/desativar compensação de recuo
- `burst_fire`: Ativar/desativar modo de tiro em rajada
- `burst_size`: Número de tiros por rajada
- `burst_delay`: Atraso entre rajadas (segundos)
- `auto_reload`: Ativar/desativar recarga automática
- `reload_ammo_threshold`: Número de tiros para acionar recarga automática

## Notas Importantes

- Este bot é apenas para fins educacionais
- Usar bots em jogos online competitivos pode violar os termos de serviço
- Sempre use de forma responsável e ética
- Considere usar apenas em modos privados/offline

## Personalizando o Modelo YOLOv8

Para melhor desempenho de detecção, treine seu modelo YOLOv8 com:
- Várias capturas de tela do jogo
- Diferentes modelos de personagens e mapas
- Condições de iluminação variadas
- Diferentes visualizações de armas

Não se esqueça de incluir rótulos de classe para que o bot possa diferenciar entre companheiros de equipe e inimigos.