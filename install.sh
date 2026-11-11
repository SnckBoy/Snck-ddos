#!/usr/bin/env bash
set -euo pipefail
REPO="https://github.com/SnckBoy/Snck-ddos.git"
BRANCH="main"
DIR="${SNCK_INSTALL_DIR:-$HOME/SNCK-Command-Center}"
PYTHON="${PYTHON:-python3}"

for bin in git "$PYTHON"; do
  command -v "$bin" >/dev/null 2>&1 || { echo "[!] Missing dependency: $bin"; exit 1; }
done

if [ -e "$DIR" ] && [ ! -d "$DIR/.git" ]; then
  echo "[!] Refusing to overwrite existing non-Git directory: $DIR"
  echo "    Choose another path with SNCK_INSTALL_DIR=/path/to/install"
  exit 1
fi

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" remote get-url origin >/dev/null
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
python -m pip install -r requirements.txt
python -m py_compile main.py command_center.py
echo
echo "[✓] SNCK Command Center installed in: $DIR"
echo "Run: cd \"$DIR\" && source .venv/bin/activate && python main.py"
echo "Dashboard: http://127.0.0.1:6666 (localhost only)"
echo "Set SNCK_TEST_ALLOWLIST to exact authorized public hosts."
echo "No firewall ports are opened."
