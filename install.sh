#!/usr/bin/env bash
# Snck-ddos installer — panel on :6767
set -euo pipefail

REPO_GIT="https://github.com/SnckBoy/Snck-ddos.git"
DIR="${HOME}/Snck-ddos"
PYTHON="${PYTHON:-python3}"

echo "[*] Snck-ddos installer"
echo "[*] install dir: ${DIR}"

for bin in git "$PYTHON"; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "[!] missing: $bin"
    exit 1
  fi
done

if [ -d "${DIR}/.git" ]; then
  echo "[*] existing clone — pulling"
  git -C "${DIR}" pull --ff-only || true
else
  rm -rf "${DIR}"
  echo "[*] cloning..."
  git clone --depth 1 "${REPO_GIT}" "${DIR}"
fi

cd "${DIR}"

if [ ! -f main.py ]; then
  echo "[!] main.py missing"
  ls -la
  exit 1
fi

echo "[*] creating venv..."
"${PYTHON}" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[*] installing packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

touch proxies.txt live_proxies.txt
mkdir -p static web/templates

if command -v g++ >/dev/null 2>&1; then
  echo "[*] building C++ L4 core..."
  (cd cpp && bash build.sh && chmod +x snck_ultra.sh 2>/dev/null || true) || true
fi

chmod +x main.py install.sh 2>/dev/null || true

echo ""
echo "[\u2713] ready"
echo ""
echo "  start:  cd ${DIR} && source .venv/bin/activate && python main.py"
echo "  panel:  http://YOUR_VPS_IP:6767"
echo "  health: http://YOUR_VPS_IP:6767/health"
echo "  firewall: sudo ufw allow 6767/tcp"
echo ""
