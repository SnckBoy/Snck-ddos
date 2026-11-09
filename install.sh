#!/usr/bin/env bash
# Snck-ddos one-cmd installer — installs ALL system + Python deps automatically
set -euo pipefail

REPO_GIT="https://github.com/SnckBoy/Snck-ddos.git"
DIR="${HOME}/Snck-ddos"
PYTHON="${PYTHON:-python3}"
PORT="${SNCK_PORT:-6767}"

echo "========================================"
echo "  Snck-ddos full installer"
echo "  dir:  ${DIR}"
echo "  port: ${PORT}"
echo "========================================"

# ---------- helpers ----------
have() { command -v "$1" >/dev/null 2>&1; }

need_root_pkg() {
  # return 0 if we should try package install
  have sudo || [ "$(id -u)" -eq 0 ]
}

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    echo "[!] need root/sudo for: $*"
    return 1
  fi
}

# ---------- detect OS + install system packages ----------
install_system_deps() {
  echo "[*] checking system packages..."

  local missing=0
  have git     || missing=1
  have "$PYTHON" || missing=1
  have g++     || true   # optional but preferred
  have curl    || missing=1

  # Always try to ensure python venv/pip modules exist on Debian family
  if have apt-get; then
    echo "[*] OS: Debian/Ubuntu (apt)"
    run_root apt-get update -y
    run_root DEBIAN_FRONTEND=noninteractive apt-get install -y \
      git curl ca-certificates \
      python3 python3-venv python3-pip python3-dev \
      build-essential g++ \
      || echo "[!] apt install had issues — continuing"
  elif have dnf; then
    echo "[*] OS: Fedora/RHEL (dnf)"
    run_root dnf install -y \
      git curl ca-certificates \
      python3 python3-pip python3-devel \
      gcc gcc-c++ make \
      || echo "[!] dnf install had issues — continuing"
  elif have yum; then
    echo "[*] OS: CentOS/RHEL (yum)"
    run_root yum install -y \
      git curl ca-certificates \
      python3 python3-pip python3-devel \
      gcc gcc-c++ make \
      || echo "[!] yum install had issues — continuing"
  elif have pacman; then
    echo "[*] OS: Arch (pacman)"
    run_root pacman -Sy --noconfirm \
      git curl ca-certificates \
      python python-pip \
      base-devel gcc \
      || echo "[!] pacman install had issues — continuing"
  elif have apk; then
    echo "[*] OS: Alpine (apk)"
    run_root apk add --no-cache \
      git curl ca-certificates \
      python3 py3-pip py3-virtualenv \
      g++ make \
      || echo "[!] apk install had issues — continuing"
  else
    echo "[!] unknown package manager — install git + python3 + g++ manually if missing"
  fi

  # re-resolve python
  if ! have "$PYTHON"; then
    if have python3; then PYTHON=python3
    elif have python; then PYTHON=python
    else
      echo "[!] python3 not found after package install"
      exit 1
    fi
  fi

  if ! have git; then
    echo "[!] git not found after package install"
    exit 1
  fi

  echo "[ok] python: $($PYTHON --version 2>&1)"
  echo "[ok] git:    $(git --version 2>&1)"
  if have g++; then
    echo "[ok] g++:    $(g++ --version 2>&1 | head -1)"
  else
    echo "[!] g++ missing — C++ ultra L4 will be skipped"
  fi
}

# ---------- firewall ----------
open_firewall() {
  echo "[*] opening TCP ${PORT}..."
  if have ufw; then
    run_root ufw allow "${PORT}/tcp" || true
    run_root ufw reload || true
    echo "[ok] ufw allowed ${PORT}/tcp"
  elif have firewall-cmd; then
    run_root firewall-cmd --permanent --add-port="${PORT}/tcp" || true
    run_root firewall-cmd --reload || true
    echo "[ok] firewalld allowed ${PORT}/tcp"
  elif have iptables; then
    run_root iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null \
      || run_root iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT || true
    echo "[ok] iptables rule for ${PORT} (may not persist reboot)"
  else
    echo "[!] no known firewall tool — open TCP ${PORT} in your cloud panel"
  fi
}

# ---------- main ----------
install_system_deps

echo "[*] fetching source..."
if [ -d "${DIR}/.git" ]; then
  git -C "${DIR}" pull --ff-only || true
else
  rm -rf "${DIR}"
  git clone --depth 1 "${REPO_GIT}" "${DIR}"
fi

cd "${DIR}"

if [ ! -f main.py ]; then
  echo "[!] main.py missing after clone"
  ls -la
  exit 1
fi

echo "[*] creating venv..."
if ! "${PYTHON}" -m venv .venv; then
  echo "[!] venv failed — trying ensurepip / reinstall python3-venv"
  if have apt-get; then
    run_root DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip || true
  fi
  "${PYTHON}" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[*] upgrading pip..."
python -m pip install -q --upgrade pip setuptools wheel || \
  python -m pip install -q --upgrade pip

echo "[*] installing Python packages from requirements.txt..."
python -m pip install -q -r requirements.txt

touch proxies.txt live_proxies.txt
mkdir -p static web/templates

if have g++; then
  echo "[*] building C++ ultra L4 core..."
  (cd cpp && bash build.sh && chmod +x snck_ultra.sh 2>/dev/null || true) \
    || echo "[!] C++ build failed — Python methods still work"
else
  echo "[!] skip C++ core (no g++)"
fi

chmod +x main.py install.sh 2>/dev/null || true
chmod +x cpp/build.sh cpp/snck_ultra.sh 2>/dev/null || true

open_firewall

# quick self-check
echo "[*] self-check imports..."
python -c "from web.app import app; print('[ok] web.app import')" || {
  echo "[!] import failed — check pip install output above"
  exit 1
}

echo ""
echo "========================================"
echo "  INSTALL COMPLETE"
echo "========================================"
echo ""
echo "  start:"
echo "    cd ${DIR}"
echo "    source .venv/bin/activate"
echo "    python main.py"
echo ""
echo "  panel:  http://YOUR_VPS_IP:${PORT}"
echo "  health: http://YOUR_VPS_IP:${PORT}/health"
echo ""
echo "  ultra L4 (optional):"
echo "    cd ${DIR}/cpp && ./snck_ultra.sh udp TARGET_IP PORT 4 64 60 1200"
echo ""
