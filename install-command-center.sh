#!/usr/bin/env bash
set -euo pipefail
REPO="https://github.com/SnckBoy/Snck-ddos.git"
DIR="\${HOME}/SNCK-Command-Center"
BRANCH="safe-command-center"
PYTHON="\${PYTHON:-python3}"
for bin in git "$PYTHON"; do command -v "$bin" >/dev/null 2>&1 || { echo "[!] Missing dependency: $bin"; exit 1; }; done
if [ -d "$DIR/.git" ]; then
 git -C "$DIR" fetch origin "$BRANCH"
 git -C "$DIR" checkout "$BRANCH"
 git -C "$DIR" pull --ff-only origin "$BRANCH"
else
 git clone --depth 1 --branch "$BRANCH" "$REPO" "$DIR"
fi
cd "$DIR"
"$PYTHON" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "fastapi>=0.110,<1" "uvicorn[standard]>=0.27,<1" "aiohttp>=3.9,<4" "pydantic>=2.6,<3"
echo
echo "[✓] SNCK Command Center installed."
echo "Run: cd \"$DIR\" && source .venv/bin/activate && python command_center.py"
echo "Dashboard: http://127.0.0.1:6666 (localhost only)"
