#!/usr/bin/env bash
# Optional OpenFOAM ESI v2312 install placeholder.
# On Brev, install from ESI packages per your license or use Foundation build.
set -euo pipefail
echo "[openclaw_engineering] OpenFOAM ESI: install per https://develop.openfoam.com/"
echo "After install, ensure 'simpleFoam' is on PATH and re-run openclaw-engineering-doctor."
if command -v simpleFoam >/dev/null 2>&1; then
  echo "simpleFoam found: $(which simpleFoam)"
  exit 0
fi
exit 0
