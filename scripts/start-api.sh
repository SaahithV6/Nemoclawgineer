#!/usr/bin/env bash
# Start openclaw-engineering-api on Brev when systemctl --user is not available (plain SSH).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${OPENCLAW_ENGINEERING_VENV:-$HOME/.local/share/openclaw-engineering/venv}"
ENV_FILE="${OPENCLAW_ENGINEERING_ENV:-$HOME/.openclaw-engineering/.env}"
STATE_DIR="${OPENCLAW_ENGINEERING_STATE:-$HOME/.local/state/openclaw-engineering}"
mkdir -p "$STATE_DIR"
if [[ ! -x "$VENV_DIR/bin/openclaw-engineering-api" ]]; then
  echo "Run ./setup.sh first (venv missing)" >&2
  exit 1
fi
if pgrep -f "openclaw-engineering-api" >/dev/null 2>&1; then
  echo "Already running. Log: $STATE_DIR/api.log"
  curl -s "http://127.0.0.1:8765/health" || true
  exit 0
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE" 2>/dev/null || true
set +a
nohup "$VENV_DIR/bin/openclaw-engineering-api" >>"$STATE_DIR/api.log" 2>&1 &
sleep 1
echo "Started. Log: $STATE_DIR/api.log"
curl -s "http://127.0.0.1:8765/health" && echo
