#!/usr/bin/env bash
set -euo pipefail

log() { printf '[openclaw_engineering] %s\n' "$*"; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

setup_user_wrapper() {
  if have_cmd simpleFoam; then
    log "simpleFoam already on PATH: $(command -v simpleFoam)"
    return 0
  fi

  local bashrc
  bashrc="$(ls -1d /usr/lib/openfoam/openfoam*/etc/bashrc 2>/dev/null | sort -V | tail -1 || true)"
  if [[ -z "$bashrc" || ! -f "$bashrc" ]]; then
    return 1
  fi

  mkdir -p "$HOME/.local/bin"
  cat > "$HOME/.local/bin/simpleFoam" <<EOF
#!/usr/bin/env bash
set -euo pipefail
source "$bashrc"
exec simpleFoam "\$@"
EOF
  chmod +x "$HOME/.local/bin/simpleFoam"
  log "Installed simpleFoam wrapper at ~/.local/bin/simpleFoam"
  export PATH="$HOME/.local/bin:$PATH"
  have_cmd simpleFoam
}

install_via_esi_repo() {
  log "Installing OpenFOAM via ESI apt repository..."
  if have_cmd curl; then
    curl -fsSL https://dl.openfoam.com/add-debian-repo.sh | sudo bash
  elif have_cmd wget; then
    wget -qO- https://dl.openfoam.com/add-debian-repo.sh | sudo bash
  else
    log "Neither curl nor wget is available to add OpenFOAM repo."
    return 1
  fi

  sudo apt-get update -qq
  local pkg
  for pkg in openfoam2312-default openfoam2306-default openfoam2212-default openfoam2206-default; do
    if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$pkg"; then
      log "Installed $pkg"
      return 0
    fi
  done
  log "Could not install an ESI OpenFOAM default package."
  return 1
}

install_via_ubuntu_repo() {
  log "Trying Ubuntu OpenFOAM packages..."
  local pkg
  for pkg in openfoam openfoam-bin; do
    if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$pkg"; then
      log "Installed $pkg"
      return 0
    fi
  done
  return 1
}

main() {
  if have_cmd simpleFoam; then
    log "simpleFoam found: $(command -v simpleFoam)"
    exit 0
  fi

  if ! have_cmd apt-get; then
    log "apt-get not found; cannot auto-install OpenFOAM"
    exit 1
  fi

  # Try ESI first, then Ubuntu fallback.
  install_via_esi_repo || install_via_ubuntu_repo || {
    log "OpenFOAM install failed. Install manually and re-run setup."
    exit 1
  }

  have_cmd simpleFoam || setup_user_wrapper || true
  if have_cmd simpleFoam; then
    log "OpenFOAM ready: $(command -v simpleFoam)"
    exit 0
  fi

  log "OpenFOAM packages installed, but simpleFoam still not on PATH."
  log "Source OpenFOAM bashrc or add ~/.local/bin to PATH, then re-run doctor."
  exit 1
}

main "$@"
