#!/usr/bin/env bash
# Snck-ddos one-command installer
# Repo hosts the full tree — clone + venv + deps
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
chmod +x main.py install.sh 2>/dev/null || true

echo ""
echo "[\u2713] Snck-ddos ready"
echo ""
echo "  start:"
echo "    cd ${DIR} && source .venv/bin/activate && python main.py"
echo ""
echo "  panel: http://0.0.0.0:6666"
echo ""
