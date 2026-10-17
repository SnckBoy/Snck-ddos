#!/usr/bin/env bash
set -euo pipefail
REPO_GIT="https://github.com/SnckBoy/Snck-ddos.git"
DIR="${HOME}/Snck-ddos"
PYTHON="${PYTHON:-python3}"
echo "[*] Snck-ddos installer -> ${DIR}"
for bin in git "$PYTHON"; do
  command -v "$bin" >/dev/null 2>&1 || { echo "[!] missing $bin"; exit 1; }
done
if [ -d "${DIR}/.git" ]; then
  echo "[*] pull"
  git -C "${DIR}" pull --ff-only || true
else
  rm -rf "${DIR}"
  git clone --depth 1 "${REPO_GIT}" "${DIR}"
fi
cd "${DIR}"
echo "[*] venv + deps"
"${PYTHON}" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
touch proxies.txt live_proxies.txt
mkdir -p static web/templates
if command -v g++ >/dev/null 2>&1; then
  echo "[*] C++ L4"
  (cd cpp && bash build.sh) || true
fi
chmod +x main.py install.sh 2>/dev/null || true
echo ""
echo "[ok] start:  cd ${DIR} && source .venv/bin/activate && python main.py"
echo "[ok] panel:  http://YOUR_VPS_IP:6767"
echo "[ok] health: http://YOUR_VPS_IP:6767/health"
echo "[ok] fw:     sudo ufw allow 6767/tcp"
echo ""
