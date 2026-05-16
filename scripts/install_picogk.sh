#!/usr/bin/env bash
# Optional PicoGK setup for OpenClaw Engineering on Brev / Ubuntu
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${HOME}/.openclaw-engineering/.env"

log() { printf '[install_picogk] %s\n' "$*"; }

if command -v apt-get >/dev/null 2>&1; then
  log "Installing .NET 9 SDK and xvfb..."
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq dotnet-sdk-9.0 xvfb || true
fi

log "Building PicoGK driver..."
dotnet build -c Release "$REPO_ROOT/picogk_driver/OpenClawEngineering.PicoGK.csproj"

mkdir -p "$(dirname "$ENV_FILE")"
touch "$ENV_FILE"
grep -q 'OPENCLAW_ENGINEERING_PICOGK_ENABLED' "$ENV_FILE" 2>/dev/null || \
  echo 'OPENCLAW_ENGINEERING_PICOGK_ENABLED=1' >> "$ENV_FILE"

log "Done. Run: openclaw-engineering-doctor"
log "If Linux runtime fails, build https://github.com/leap71/PicoGKRuntime and set PICOGK_RUNTIME_PATH"
