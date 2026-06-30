# Semaphore Agent

Semáforo visual pinado na tela para saber quando agentes de IA terminam, precisam de atenção ou estão executando tarefas.

**v0.2.0** — daemon/UI separados, tray (subprocesso GTK3), ocultar overlay (só bandeja), alertas desktop, layouts, histórico, hooks Cursor v4.

## Estados das luzes

| Luz | Significado |
|-----|-------------|
| Cinza (apagado) | Nenhum agente ativo |
| Vermelho fixo | Executando ativamente |
| Vermelho piscando | Ação bloqueante urgente (comando sensível, permissão negada) |
| Amarelo fixo | Aguardando — build/teste **ou** sua aprovação no Cursor |
| Verde fixo | Tarefa concluída (~45s, depois volta ao cinza) |

## Controles do semáforo

| Ação | Como |
|------|------|
| Mover | Clique esquerdo + arrastar |
| Detalhes + histórico | Clique direito |
| Marcar como visto | Duplo clique esquerdo ou `semaphore dismiss` |
| Ocultar (só bandeja) | Ícone `−` no canto superior direito do overlay |
| Mostrar overlay de novo | Tray → **Mostrar semáforo** ou `semaphore raise` |
| Atalho global | `./scripts/register-shortcut.sh` (padrão: Super+Shift+S → dismiss) |

### Modo só bandeja

Você pode tirar o semáforo da tela e acompanhar o status **apenas pelo ícone na bandeja do sistema** (emoji 🔴🟡🟢⚫):

1. Clique no **`−`** no overlay — a janela some; o daemon e o tray continuam rodando.
2. O tray segue atualizando estado e emoji a cada ~800 ms.
3. Para ver o overlay de novo: tray → **Mostrar semáforo** ou `semaphore raise`.

> Ocultar **não** para o daemon nem desliga notificações/sons. O overlay **não reaparece sozinho** quando um agente muda de estado — só quando você pedir no tray ou via CLI.

**Alternativa permanente** (sem widget na tela desde o início): em `config.toml`, `overlay_enabled = false` e `tray_enabled = true`. O tray continua ativo; use **Mostrar semáforo** se quiser o overlay temporariamente (requer `overlay_enabled = true` + restart da UI).

## Arquitetura

```
┌─────────────────┐     Unix socket      ┌──────────────────┐
│  Cursor hooks   │ ──────────────────► │  semaphore       │
│  Claude / Codex │                     │  daemon          │
│  process scan   │                     │  (headless)      │
└─────────────────┘                     └────────┬─────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
             notify-send                   status.json                  semaphore ui
             + som done                    (fallback)                   overlay GTK4
                                                                          + tray GTK3
```

- **Daemon** — IPC, adapters, alertas, persistência (`semaphore daemon`)
- **UI** — overlay + tray; faz polling do daemon (`semaphore ui`)
- **Tray** — roda em subprocesso GTK3 (AppIndicator não convive com GTK4 no mesmo processo)

## Requisitos

- Linux (Wayland ou X11)
- Python 3.11+
- **PyGObject + GTK4** (overlay)
- **Ayatana AppIndicator3** (tray no GNOME — pacote do sistema, typelib em `/usr/lib/...`)
- **wmctrl**, **libnotify-bin** (recomendado)

### Modos de overlay

| Ambiente | Modo | Prioridade sobre apps |
|----------|------|------------------------|
| KDE / Hyprland / Sway | gtk4-layer-shell | Sim (camada OVERLAY) |
| **Zorin / GNOME Wayland** | fallback GTK + XWayland | Parcial (`keep_above` + EWMH) |

> No **Zorin OS 18 (Ubuntu 24.04)** o pacote `gtk4-layer-shell` **não existe no apt**.  
> Mesmo compilando da fonte, **GNOME não suporta layer-shell**. O semáforo usa `GDK_BACKEND=x11` automaticamente.

### Debian / Ubuntu / Zorin

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 libgtk-4-1
sudo apt install gir1.2-ayatanaappindicator3-0.1  # tray
sudo apt install wmctrl libnotify-bin
```

### Python

- Python **3.11+**
- [uv](https://docs.astral.sh/uv/) para instalar o pacote (`uv pip install -e .`)

**Opção A — Conda** (recomendado; `environment.yml` traz PyGObject/GTK4):

```bash
conda env create -f environment.yml   # cria o env semaphore-agent
conda activate semaphore-agent
uv pip install -e .
```

**Opção B — venv + pacotes do sistema** (após o `apt install` acima):

```bash
python3 -m venv .venv
source .venv/bin/activate
uv pip install -e .
```

## Instalação

```bash
git clone https://github.com/MiessiGomes/semaphore_agent.git
cd semaphore_agent

# Ative o ambiente Python (conda ou venv — ver seção anterior)
conda activate semaphore-agent   # ou: source .venv/bin/activate

uv pip install -e .

semaphore install-hooks --force   # copia hooks para ~/.cursor/
semaphore start                   # teste manual (opcional)
```

Atalho global (GNOME):

```bash
chmod +x scripts/register-shortcut.sh
./scripts/register-shortcut.sh
```

Após `install-hooks`, **reinicie o Cursor** (ou abra um chat Agent novo).

## Systemd (recomendado — inicia no login)

Instala daemon + UI como serviços **user** (sem sudo). Rode com o ambiente Python ativo (conda ou venv):

```bash
conda activate semaphore-agent   # ou: source .venv/bin/activate
./scripts/install-systemd.sh split --start
```

| Modo | Comando | Serviços |
|------|---------|----------|
| **split** (recomendado) | `./scripts/install-systemd.sh split --start` | `semaphore-agent-daemon` + `semaphore-agent-ui` |
| combined | `./scripts/install-systemd.sh combined --start` | `semaphore-agent` (`semaphore start`) |

O script:

- Detecta Python na ordem: `SEMAPHORE_PYTHON` → conda ativo → `.venv` do repo → env `semaphore-agent` → `python3` no PATH
- Grava units em `~/.config/systemd/user/`
- Grava `~/.config/semaphore_agent/systemd.env` (`GDK_BACKEND`, `GI_TYPELIB_PATH`, `PATH`)
- Importa variáveis voláteis da sessão gráfica (`DISPLAY`, `XAUTHORITY`, etc.) para o `systemctl --user` — **não** as fixa no env file (evita quebrar após relogin)

Se o overlay não subir após relogin:

```bash
systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR
systemctl --user restart semaphore-agent-ui.service
```

Ou reinstale a partir de um terminal na sessão gráfica: `./scripts/install-systemd.sh split --start`

### Comandos do dia a dia

```bash
systemctl --user status semaphore-agent-daemon.service
systemctl --user status semaphore-agent-ui.service
systemctl --user restart semaphore-agent-daemon.service semaphore-agent-ui.service
journalctl --user -u semaphore-agent-ui.service -f
systemctl --user stop semaphore-agent-daemon.service semaphore-agent-ui.service
```

**Não rode `semaphore start` manualmente enquanto o systemd estiver ativo** — conflita no socket.

### Atualizar após mudanças no código

Fluxo completo quando você puxa ou edita o projeto:

```bash
cd semaphore_agent   # diretório do clone
conda activate semaphore-agent   # ou: source .venv/bin/activate

uv pip install -e .                    # reinstala pacote (editable)
semaphore install-hooks --force        # atualiza ~/.cursor/hooks/ (se hooks mudaram)

pkill -f "semaphore (daemon|ui|start)" 2>/dev/null || true
systemctl --user restart semaphore-agent-daemon.service semaphore-agent-ui.service

semaphore status                       # confere estado + versão dos hooks
```

| O que mudou | O que fazer |
|-------------|-------------|
| Código Python (`.py`) | `uv pip install -e .` + restart systemd |
| Hooks (`hooks/`) | `semaphore install-hooks --force` + reiniciar Cursor |
| Units systemd (`systemd/`) | `./scripts/install-systemd.sh split -y --start` |

Se mudou só Python e já usa `uv pip install -e .`, basta `systemctl --user restart ...`.

## Rodar manualmente (sem systemd)

```bash
semaphore start          # daemon + overlay + tray
# ou separado:
semaphore daemon &
GDK_BACKEND=x11 semaphore ui
```

## CLI

```bash
semaphore start              # daemon + UI
semaphore daemon             # hub headless (IPC + adapters + alertas)
semaphore ui                 # overlay + tray (requer daemon)
semaphore status             # JSON + estado + versão dos hooks
semaphore watch              # monitora mudanças no terminal
semaphore dismiss            # marcar como visto (idle)
semaphore raise              # mostra overlay oculto (tray / wmctrl)
semaphore notify -s cli -t running -d "teste"
semaphore set done           # atalho manual
semaphore install-hooks      # hooks Cursor em ~/.cursor/
semaphore config --show
semaphore config --layout compact --anchor top-left
```

## Integrações

| Agente | Método |
|--------|--------|
| **Cursor (IDE)** | Hooks em `~/.cursor/hooks.json` via `install-hooks` |
| **Cursor CLI** (`agent` no terminal / VS Code) | Adapter `cursor-cli` (processo + `~/.cursor/chats/`) |
| **Claude Code** | Poll `claude agents --json` |
| **Codex** | Atividade em `~/.codex/sessions/` |
| **Gemini / outros** | Scanner de processos (heurístico, TTL curto) |
| **Manus / web** | Manual: `semaphore set <state>` |

### Fluxo Cursor (hooks v4)

| Evento | Estado |
|--------|--------|
| `sessionStart` | running |
| `preToolUse` (Shell/MCP/Write) | **waiting** (amarelo — aguardando aprovação) |
| `postToolUse` | running |
| `beforeShellExecution` | waiting (builds) / **attention** (sensível) |
| `beforeMCPExecution` | waiting |
| `afterShellExecution` | running |
| `afterAgentResponse` | **waiting** (agente parou; pode precisar de ação sua) |
| `postToolUseFailure` (permission_denied) | attention |
| `stop` (status=completed) | **done** (verde) |
| `sessionEnd` | idle |

Verifique a versão instalada: `semaphore status` → `Hooks Cursor: v4 (ok)`.

Heurísticos (`proc:*`) não sobrescrevem fontes confirmadas como Cursor.

### Cursor CLI (`agent` no terminal)

Os hooks do IDE **não cobrem** o comando `agent` no terminal integrado do VS Code/Cursor.  
O adapter **`cursor-cli`** detecta atividade por arquivos (não por processo — agents em background ficam abertos):

- alterações em `~/.cursor/chats/` ou `agent-transcripts/` → **vermelho**
- pausa entre etapas (>12s sem escrita) → **amarelo** breve
- fim da sessão → **verde** + notificação
- `cursor-askpass` → **vermelho piscando**

Requer `adapters.cursor = true` (padrão). Após atualizar:

```bash
uv pip install -e .
systemctl --user restart semaphore-agent-daemon.service
```

## Configuração

Arquivo: `~/.config/semaphore_agent/config.toml`

```toml
[ui]
anchor = "top-right"
margin_x = 16
margin_y = 16
layout = "vertical"   # vertical | horizontal | compact
tray_enabled = true
overlay_enabled = true
# window_x / window_y — posição salva ao arrastar

[timing]
done_timeout = 45.0
cursor_done_timeout = 45.0
claude_done_timeout = 60.0
heuristic_ttl = 15.0
stay_on_top_ms = 500

[alerts]
desktop_notifications = true
notify_on_done = true
notify_on_attention = true
sound_on_done = true
sound_file = ""
global_shortcut = "<Super><Shift>s"

[adapters]
cursor = true
claude = true
codex = true
process = true
```

Som customizado: `~/.config/semaphore_agent/done.wav`.

## UI

- Layouts: **vertical**, **horizontal**, **compact** (uma luz)
- Botão **`−`** no canto superior direito — oculta o overlay (modo só bandeja)
- Janela de detalhes com histórico (últimas 10 transições) — clique direito no overlay
- Badge numérico quando 2+ agentes ativos
- **Tray** (subprocesso GTK3; log: `Tray: ativo (subprocesso GTK3)`):
  - Emoji de estado (🔴🟡🟢⚫)
  - **Mostrar semáforo** — restaura overlay oculto
  - **Marcar como visto** — equivalente a `semaphore dismiss`

## Alertas

- `notify-send` em **done** e **attention**
- Som em **done** (`paplay`/`aplay`, ou `done.wav` customizado)

## Socket IPC

`$XDG_RUNTIME_DIR/semaphore_agent/status.sock`

```json
{"action": "update", "source": "cursor", "state": "waiting", "detail": "aprovar shell: npm test"}
{"action": "get"}
{"action": "dismiss"}
```

Estados: `idle`, `running`, `waiting`, `attention`, `done`.

Prioridade na agregação: `attention` > `running` > `waiting` > `done` > `idle`.

## Desenvolvimento

```bash
conda activate semaphore-agent   # ou: source .venv/bin/activate
uv pip install -e ".[dev]"
pytest tests/ -q
ruff check semaphore tests
```

## Licença

MIT
