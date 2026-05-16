#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NEMCLAW_DRY_RUN=1
cd "$REPO_ROOT"
python3 scripts/gen_sample_stl.py
VENV="${NEMCLAW_VENV:-$HOME/.local/share/nemoclaw/venv}"
if [[ -x "$VENV/bin/nemoclaw" ]]; then
  PY="$VENV/bin/nemoclaw"
else
  pip install -e . -q
  PY="nemoclaw"
fi
$PY run "Minimize mass, max stress 200 MPa, 500 N tensile load" \
  --stl tests/fixtures/sample_bracket.stl \
  --wait
echo "Artifacts in ~/.local/state/nemoclaw/jobs/ — see latest REPORT.md"
