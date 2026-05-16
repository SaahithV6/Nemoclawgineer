#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${NEMCLAW_VENV:-$HOME/.local/share/nemoclaw/venv}"
ENV_DIR="$HOME/.nemoclaw"
ENV_FILE="$ENV_DIR/.env"
STATE_DIR="$HOME/.local/state/nemoclaw"
USER_SYSTEMD="$HOME/.config/systemd/user"
SKILL_DST="$HOME/.openclaw/skills/nemoclaw"
OPENCLAW_JSON="$HOME/.openclaw/openclaw.json"

log() { printf '[nemoclaw] %s\n' "$*"; }

install_apt_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    log "apt-get not found; skip system packages"
    return
  fi
  log "Installing system packages (sudo)..."
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-venv python3-pip git jq curl parallel \
    gmsh calculix-ccx freecad-python3 \
    || log "Some packages failed; continue with available tools"
  if ! command -v simpleFoam >/dev/null 2>&1; then
    log "OpenFOAM not found via apt; optional CFD may use synthetic metrics"
  fi
}

setup_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  pip install -U pip wheel
  pip install -e "$REPO_ROOT"
}

setup_env_file() {
  mkdir -p "$ENV_DIR" "$STATE_DIR"
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$REPO_ROOT/.env.example" "$ENV_FILE"
    log "Created $ENV_FILE — edit tokens before Discord/OpenClaw use"
  fi
  if [[ -f "$HOME/.openclaw/.env" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$HOME/.openclaw/.env" 2>/dev/null || true
    set +a
    grep -q '^OPENCLAW_API_TOKEN=' "$ENV_FILE" 2>/dev/null || {
      tok="$(grep -E '^OPENCLAW.*TOKEN=' "$HOME/.openclaw/.env" | head -1 | cut -d= -f2- || true)"
      if [[ -n "${tok:-}" ]]; then
        echo "OPENCLAW_API_TOKEN=$tok" >> "$ENV_FILE"
      fi
    }
  fi
}

merge_openclaw_mcp() {
  mkdir -p "$(dirname "$OPENCLAW_JSON")"
  if [[ ! -f "$OPENCLAW_JSON" ]]; then
    echo '{}' > "$OPENCLAW_JSON"
  fi
  export NEMCLAW_VENV_PYTHON="$VENV_DIR/bin/python"
  export OPENCLAW_JSON
  python3 <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ["OPENCLAW_JSON"])
data = json.loads(p.read_text() or "{}")
plugins = data.setdefault("plugins", {})
bridge = plugins.setdefault("mcp-bridge", {})
servers = bridge.setdefault("servers", [])
entry = {
    "name": "nemoclaw",
    "type": "stdio",
    "command": os.environ["NEMCLAW_VENV_PYTHON"],
    "args": ["-m", "nemoclaw.mcp_server"],
}
if not any(s.get("name") == "nemoclaw" for s in servers):
    servers.append(entry)
p.write_text(json.dumps(data, indent=2))
print("Merged nemoclaw MCP server into", p)
PY
}

install_skill() {
  mkdir -p "$SKILL_DST"
  cp "$REPO_ROOT/skills/nemoclaw/SKILL.md" "$SKILL_DST/SKILL.md"
  log "Installed OpenClaw skill -> $SKILL_DST"
}

install_systemd_units() {
  mkdir -p "$USER_SYSTEMD"
  cat > "$USER_SYSTEMD/nemoclaw-api.service" <<EOF
[Unit]
Description=Nemoclaw API
After=network.target

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
WorkingDirectory=$REPO_ROOT
ExecStart=$VENV_DIR/bin/nemoclaw-api
Restart=on-failure

[Install]
WantedBy=default.target
EOF

  cat > "$USER_SYSTEMD/nemoclaw-discord.service" <<EOF
[Unit]
Description=Nemoclaw Discord bot
After=nemoclaw-api.service
Requires=nemoclaw-api.service

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
WorkingDirectory=$REPO_ROOT
ExecStart=$VENV_DIR/bin/nemoclaw-discord
Restart=on-failure

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload || true
  systemctl --user enable nemoclaw-api.service 2>/dev/null || true
  systemctl --user restart nemoclaw-api.service 2>/dev/null || {
    log "Starting API in background (no systemd)"
    nohup "$VENV_DIR/bin/nemoclaw-api" > "$STATE_DIR/api.log" 2>&1 &
  }
  if grep -q '^DISCORD_BOT_TOKEN=.\+' "$ENV_FILE" 2>/dev/null; then
    systemctl --user enable nemoclaw-discord.service 2>/dev/null || true
    systemctl --user restart nemoclaw-discord.service 2>/dev/null || true
  else
    log "Discord token empty; skip discord service"
  fi
}

main() {
  log "Nemoclaw setup (repo: $REPO_ROOT)"
  install_apt_packages
  setup_venv
  setup_env_file
  merge_openclaw_mcp
  install_skill
  install_systemd_units
  log "Run: $VENV_DIR/bin/nemoclaw-doctor"
  log "Dry test: NEMCLAW_DRY_RUN=1 $VENV_DIR/bin/nemoclaw-doctor --dry-test"
}

main "$@"
