#!/usr/bin/env bash
# Snck-ddos one-command installer
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

# build C++ L4 core if g++ present
if command -v g++ >/dev/null 2>&1; then
  echo "[*] building C++ L4 core..."
  (cd cpp && bash build.sh) || echo "[!] C++ build failed — Python L4 still works"
else
  echo "[!] g++ not found — skip C++ core (Python L4 only)"
fi

chmod +x main.py install.sh 2>/dev/null || true

echo ""
echo "[\u2713] Snck-ddos ready"
echo ""
echo "  start:"
echo "    cd ${DIR} && source .venv/bin/activate && python main.py"
echo ""
echo "  panel: http://0.0.0.0:6666"
echo ""
