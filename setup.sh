#!/usr/bin/env bash
# OpenClaw Engineering setup for NVIDIA Brev (Ubuntu 24.04, 64 CPU / 512 GB RAM)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${OPENCLAW_ENGINEERING_VENV:-$HOME/.local/share/openclaw-engineering/venv}"
ENV_DIR="$HOME/.openclaw-engineering"
ENV_FILE="$ENV_DIR/.env"
STATE_DIR="$HOME/.local/state/openclaw-engineering"
APPS_DIR="${OPENCLAW_ENGINEERING_APPS:-$HOME/.local/share/openclaw-engineering/apps}"
USER_SYSTEMD="$HOME/.config/systemd/user"
SKILL_DST="$HOME/.openclaw/skills/openclaw-engineering"
OPENCLAW_JSON="$HOME/.openclaw/openclaw.json"
RESET_ENV=0
PYTHON_BIN="${OPENCLAW_ENGINEERING_PYTHON:-}"

# FreeCAD AppImage (optional — Build123d is the primary CAD path)
FREECAD_APPIMAGE_URL="${FREECAD_APPIMAGE_URL:-https://github.com/FreeCAD/FreeCAD/releases/download/1.0.0/FreeCAD_1.0.0-Linux-x86_64.AppImage}"
FREECAD_APPIMAGE_URL_ALT="https://github.com/FreeCAD/FreeCAD/releases/download/1.1.1/FreeCAD_1.1.1-Linux-x86_64-py311.AppImage"

log() { printf '[openclaw_engineering] %s\n' "$*"; }

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --reset)
        RESET_ENV=1
        ;;
      --help|-h)
        cat <<'EOF'
Usage: ./setup.sh [--reset]

Options:
  --reset   Remove executor venv + runtime state before reinstall.
EOF
        exit 0
        ;;
      *)
        log "Unknown argument: $1"
        exit 2
        ;;
    esac
    shift
  done
}

python_meets_requirement() {
  local bin="$1"
  "$bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'
}

ensure_python_runtime() {
  local candidates=()
  [[ -n "$PYTHON_BIN" ]] && candidates+=("$PYTHON_BIN")
  candidates+=("python3.12" "python3.11" "python3")

  for cand in "${candidates[@]}"; do
    if command -v "$cand" >/dev/null 2>&1 && python_meets_requirement "$cand"; then
      PYTHON_BIN="$(command -v "$cand")"
      log "Using Python: $PYTHON_BIN ($("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")'))"
      return 0
    fi
  done

  if command -v apt-get >/dev/null 2>&1; then
    log "Python >=3.11 not found. Installing python3.11 (sudo)..."
    if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.11 python3.11-venv; then
      log "Direct install failed; trying deadsnakes PPA for Ubuntu 22.04..."
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq software-properties-common
      sudo add-apt-repository -y ppa:deadsnakes/ppa
      sudo apt-get update -qq
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.11 python3.11-venv
    fi
    if command -v python3.11 >/dev/null 2>&1 && python_meets_requirement python3.11; then
      PYTHON_BIN="$(command -v python3.11)"
      log "Using Python: $PYTHON_BIN ($("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")'))"
      return 0
    fi
  fi

  log "ERROR: Could not provision Python >=3.11. Set OPENCLAW_ENGINEERING_PYTHON to a valid interpreter."
  exit 1
}

reset_environment() {
  if [[ "$RESET_ENV" -ne 1 ]]; then
    return 0
  fi
  log "Reset requested: stopping API + clearing venv/runtime state"
  pkill -f "openclaw-engineering-api" >/dev/null 2>&1 || true
  rm -rf "$VENV_DIR" "$STATE_DIR"
  mkdir -p "$STATE_DIR"
}

install_apt_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    log "apt-get not found; skip system packages"
    return
  fi
  log "Installing system packages (sudo)..."
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-venv python3-pip git jq curl parallel wget software-properties-common \
    gmsh calculix-ccx xvfb libgl1 libxrender1 libsm6 \
    libocct-foundation-dev libocct-modeling-algorithms-dev \
    || log "Some apt packages failed; continuing"
  # NOTE: Do NOT install freecad-python3 from apt — use AppImage only (per Brev/Ubuntu 24.04)
}

install_freecad_appimage() {
  mkdir -p "$APPS_DIR"
  local target="$APPS_DIR/FreeCAD.AppImage"
  local binlink="$HOME/.local/bin/freecadcmd"
  if [[ -x "$target" ]]; then
    log "FreeCAD AppImage already present: $target"
  else
    log "Downloading FreeCAD AppImage (optional)..."
    if ! wget -q --show-progress -O "$target" "$FREECAD_APPIMAGE_URL"; then
      log "Primary URL failed, trying weekly build..."
      wget -q --show-progress -O "$target" "$FREECAD_APPIMAGE_URL_ALT" || true
    fi
    if [[ ! -s "$target" ]]; then
      rm -f "$target"
      log "WARN: FreeCAD AppImage skipped (optional). CAD uses Build123d/sculpt engine."
      log "      To add later: wget -O $target <AppImage URL>"
      return 0
    fi
    chmod +x "$target"
  fi
  if [[ ! -x "$target" ]]; then
    return 0
  fi
  mkdir -p "$HOME/.local/bin"
  cat > "$binlink" <<'WRAP'
#!/usr/bin/env bash
# Wrapper: run FreeCAD AppImage in console/batch mode
APPIMAGE="${OPENCLAW_ENGINEERING_FREECAD_APPIMAGE:-HOME_PLACEHOLDER/.local/share/openclaw-engineering/apps/FreeCAD.AppImage}"
APPIMAGE="${APPIMAGE/HOME_PLACEHOLDER/$HOME}"
export APPIMAGE
exec "$APPIMAGE" --console "$@"
WRAP
  sed -i "s|HOME_PLACEHOLDER|$HOME|g" "$binlink"
  chmod +x "$binlink"
  log "FreeCAD CLI wrapper: $binlink"
  grep -q 'OPENCLAW_ENGINEERING_FREECAD_APPIMAGE' "$ENV_FILE" 2>/dev/null || \
    echo "OPENCLAW_ENGINEERING_FREECAD_APPIMAGE=$target" >> "$ENV_FILE"
}

install_openfoam_esi() {
  if command -v foamRun >/dev/null 2>&1 || command -v simpleFoam >/dev/null 2>&1; then
    log "OpenFOAM already on PATH"
    return
  fi
  log "Installing OpenFOAM Foundation (openfoam13) from dl.openfoam.org..."
  sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key > /etc/apt/trusted.gpg.d/openfoam.asc"
  if ! grep -qs "dl\\.openfoam\\.org/ubuntu" "/etc/apt/sources.list" 2>/dev/null \
    && ! grep -Rqs "dl\\.openfoam\\.org/ubuntu" "/etc/apt/sources.list.d" 2>/dev/null; then
    sudo add-apt-repository -y http://dl.openfoam.org/ubuntu
  else
    log "OpenFOAM apt repository already configured"
  fi
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openfoam13 || {
    log "OpenFOAM install failed — strict CFD runs will fail until simpleFoam is installed"
    return
  }
  if command -v foamRun >/dev/null 2>&1; then
    log "OpenFOAM installed: $(command -v foamRun)"
  elif command -v simpleFoam >/dev/null 2>&1; then
    log "OpenFOAM installed: $(command -v simpleFoam)"
  else
    log "OpenFOAM package installed but solver binaries are not on current PATH."
    log "Add to shell profile: source /opt/openfoam13/etc/bashrc"
  fi
}

setup_venv() {
  local recreate=0
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    if ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      log "Existing venv uses Python <3.11; recreating venv."
      recreate=1
    fi
  fi
  if [[ "$recreate" -eq 1 ]]; then
    rm -rf "$VENV_DIR"
  fi
  if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  "$VENV_DIR/bin/python" -m pip install -U pip wheel
  "$VENV_DIR/bin/python" -m pip install -e "$REPO_ROOT"
  log "Python stack: build123d, cadquery, optuna, pyvista, httpx, ..."
}

setup_env_file() {
  mkdir -p "$ENV_DIR" "$STATE_DIR"
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$REPO_ROOT/.env.example" "$ENV_FILE"
    log "Created $ENV_FILE — fill OnShape, Discord, SMTP, OpenClaw tokens"
  fi
  if [[ -f "$HOME/.openclaw/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$HOME/.openclaw/.env" 2>/dev/null || true
    set +a
    grep -q '^OPENCLAW_API_TOKEN=' "$ENV_FILE" 2>/dev/null || {
      tok="$(grep -E '^OPENCLAW.*TOKEN=' "$HOME/.openclaw/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)"
      [[ -n "${tok:-}" ]] && echo "OPENCLAW_API_TOKEN=$tok" >> "$ENV_FILE"
    }
    grep -q '^OPENCLAW_GATEWAY_URL=' "$ENV_FILE" 2>/dev/null || {
      url="$(grep -E '^OPENCLAW.*URL=' "$HOME/.openclaw/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)"
      [[ -n "${url:-}" ]] && echo "OPENCLAW_GATEWAY_URL=$url" >> "$ENV_FILE"
    }
  fi
}

merge_openclaw_mcp() {
  mkdir -p "$(dirname "$OPENCLAW_JSON")"
  [[ -f "$OPENCLAW_JSON" ]] || echo '{}' > "$OPENCLAW_JSON"
  export OPENCLAW_ENGINEERING_VENV_PYTHON="$VENV_DIR/bin/python" OPENCLAW_JSON
  "$PYTHON_BIN" <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ["OPENCLAW_JSON"])
data = json.loads(p.read_text() or "{}")
plugins = data.setdefault("plugins", {})
bridge = plugins.setdefault("mcp-bridge", {})
servers = bridge.setdefault("servers", [])
entry = {
    "name": "openclaw-engineering",
    "type": "stdio",
    "command": os.environ["OPENCLAW_ENGINEERING_VENV_PYTHON"],
    "args": ["-m", "openclaw_engineering.mcp_server"],
}
names = {s.get("name") for s in servers}
if "openclaw-engineering" not in names:
    servers.append(entry)
p.write_text(json.dumps(data, indent=2))
print("Merged openclaw-engineering MCP into", p)
PY
}

install_skill() {
  mkdir -p "$SKILL_DST"
  cp "$REPO_ROOT/skills/openclaw-engineering/SKILL.md" "$SKILL_DST/SKILL.md"
  log "OpenClaw skill -> $SKILL_DST"
}

start_api_nohup() {
  mkdir -p "$STATE_DIR"
  if pgrep -f "openclaw-engineering-api" >/dev/null 2>&1; then
    log "openclaw-engineering-api already running (pgrep)"
    return 0
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE" 2>/dev/null || true
  set +a
  nohup "$VENV_DIR/bin/openclaw-engineering-api" > "$STATE_DIR/api.log" 2>&1 &
  sleep 1
  log "API started via nohup — log: $STATE_DIR/api.log"
  log "Health: curl -s http://127.0.0.1:8765/health"
}

install_systemd_units() {
  mkdir -p "$USER_SYSTEMD"
  cat > "$USER_SYSTEMD/openclaw-engineering-api.service" <<EOF
[Unit]
Description=OpenClaw Engineering API
After=network.target

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
WorkingDirectory=$REPO_ROOT
ExecStart=$VENV_DIR/bin/openclaw-engineering-api
Restart=on-failure

[Install]
WantedBy=default.target
EOF
  if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" && -n "${XDG_RUNTIME_DIR:-}" ]] && systemctl --user daemon-reload 2>/dev/null; then
    systemctl --user enable openclaw-engineering-api.service 2>/dev/null || true
    if systemctl --user restart openclaw-engineering-api.service 2>/dev/null; then
      log "API: systemd user unit openclaw-engineering-api.service"
      return 0
    fi
  fi
  log "systemctl --user unavailable in this SSH session (no DBUS). Starting API with nohup."
  log "For persistent user units on Brev: loginctl enable-linger \$USER  (once), then re-login."
  start_api_nohup
  log "Or run: $REPO_ROOT/scripts/start-api.sh"
}

main() {
  parse_args "$@"
  log "=== OpenClaw Engineering setup (Brev) ==="
  log "Repo: $REPO_ROOT"
  install_apt_packages
  ensure_python_runtime
  reset_environment
  setup_env_file
  install_freecad_appimage
  setup_venv
  install_openfoam_esi
  merge_openclaw_mcp
  install_skill
  install_systemd_units
  log ""
  log "Next steps:"
  log "  1. Edit $ENV_FILE (OnShape only; Gmail/Discord via OpenClaw)"
  log "  2. openclaw config patch --file config/openclaw.discord.patch.json5"
  log "  3. openclaw config patch --file config/openclaw.hooks.patch.json5"
  log "  4. openclaw webhooks gmail setup --account you@gmail.com"
  log "  5. $VENV_DIR/bin/openclaw-engineering-doctor"
  log "  6. Read docs/SETUP.md"
}

main "$@"
