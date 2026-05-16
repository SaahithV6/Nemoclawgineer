#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OPENCLAW_ENGINEERING_DRY_RUN=1
cd "$REPO_ROOT"
python3 scripts/gen_sample_stl.py
VENV="${OPENCLAW_ENGINEERING_VENV:-$HOME/.local/share/openclaw-engineering/venv}"
if [[ -x "$VENV/bin/openclaw-engineering" ]]; then
  PY="$VENV/bin/openclaw-engineering"
else
  pip install -e . -q
  PY="openclaw-engineering"
fi
$PY run "Minimize mass, max stress 200 MPa, 500 N tensile load" \
  --stl tests/fixtures/sample_bracket.stl \
  --wait
echo "Artifacts in ~/.local/state/openclaw-engineering/jobs/ — see latest REPORT.md"
