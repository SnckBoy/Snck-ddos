#!/usr/bin/env bash
# Snck-ddos one-cmd installer — system + Python + C++ + firewall
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

have() { command -v "$1" >/dev/null 2>&1; }

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

# Use env so DEBIAN_FRONTEND works when run via run_root ("$@" breaks VAR=val cmd)
apt_install() {
  run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

install_system_deps() {
  echo "[*] checking system packages..."

  if have apt-get; then
    echo "[*] OS: Debian/Ubuntu (apt)"
    run_root apt-get update -y
    # python3-venv is REQUIRED on Ubuntu or `python3 -m venv` fails (ensurepip missing)
    apt_install \
      git curl ca-certificates \
      python3 python3-venv python3-pip python3-dev \
      build-essential g++ \
      || true
    # versioned venv package (Ubuntu 24.04 = 3.12)
    PYVER="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "3")"
    apt_install "python${PYVER}-venv" || apt_install python3-venv || true
  elif have dnf; then
    echo "[*] OS: Fedora/RHEL (dnf)"
    run_root dnf install -y \
      git curl ca-certificates \
      python3 python3-pip python3-devel \
      gcc gcc-c++ make || true
  elif have yum; then
    echo "[*] OS: CentOS/RHEL (yum)"
    run_root yum install -y \
      git curl ca-certificates \
      python3 python3-pip python3-devel \
      gcc gcc-c++ make || true
  elif have pacman; then
    echo "[*] OS: Arch (pacman)"
    run_root pacman -Sy --noconfirm \
      git curl ca-certificates python python-pip base-devel gcc || true
  elif have apk; then
    echo "[*] OS: Alpine (apk)"
    run_root apk add --no-cache \
      git curl ca-certificates python3 py3-pip py3-virtualenv g++ make || true
  else
    echo "[!] unknown package manager — install git + python3 + python3-venv + g++ manually"
  fi

  if ! have "$PYTHON"; then
    if have python3; then PYTHON=python3
    elif have python; then PYTHON=python
    else
      echo "[!] python3 not found"
      exit 1
    fi
  fi
  if ! have git; then
    echo "[!] git not found"
    exit 1
  fi

  echo "[ok] python: $($PYTHON --version 2>&1)"
  echo "[ok] git:    $(git --version 2>&1)"
  if have g++; then
    echo "[ok] g++:    $(g++ --version 2>&1 | head -1)"
  else
    echo "[!] g++ missing — C++ ultra L4 skipped"
  fi
}

open_firewall() {
  echo "[*] opening TCP ${PORT}..."
  if have ufw; then
    run_root ufw allow "${PORT}/tcp" || true
    run_root ufw reload || true
    echo "[ok] ufw ${PORT}/tcp"
  elif have firewall-cmd; then
    run_root firewall-cmd --permanent --add-port="${PORT}/tcp" || true
    run_root firewall-cmd --reload || true
    echo "[ok] firewalld ${PORT}/tcp"
  elif have iptables; then
    run_root iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null \
      || run_root iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT || true
    echo "[ok] iptables ${PORT}"
  else
    echo "[!] open TCP ${PORT} in cloud security group / firewall panel"
  fi
}

make_venv() {
  echo "[*] creating venv..."
  rm -rf .venv
  if "${PYTHON}" -m venv .venv; then
    return 0
  fi
  echo "[!] venv failed — installing python3-venv / ensurepip again"
  if have apt-get; then
    PYVER="$("${PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "3")"
    apt_install "python${PYVER}-venv" python3-venv python3-pip || true
  fi
  rm -rf .venv
  if ! "${PYTHON}" -m venv .venv; then
    echo "[!] trying virtualenv fallback"
    "${PYTHON}" -m pip install --break-system-packages -q virtualenv 2>/dev/null \
      || "${PYTHON}" -m pip install -q virtualenv 2>/dev/null || true
    if have virtualenv; then
      virtualenv -p "$PYTHON" .venv
    else
      "${PYTHON}" -m virtualenv .venv
    fi
  fi
  if [ ! -x .venv/bin/python ]; then
    echo "[!] FATAL: could not create venv"
    exit 1
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
  echo "[!] main.py missing"
  ls -la
  exit 1
fi

make_venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[*] upgrading pip..."
python -m pip install -q --upgrade pip setuptools wheel || python -m pip install -q --upgrade pip

echo "[*] installing Python packages..."
python -m pip install -q -r requirements.txt

touch proxies.txt live_proxies.txt
mkdir -p static web/templates

if have g++; then
  echo "[*] building C++ ultra L4..."
  (cd cpp && bash build.sh && chmod +x snck_ultra.sh 2>/dev/null || true) \
    || echo "[!] C++ build failed — Python methods still work"
else
  echo "[!] skip C++ core"
fi

chmod +x main.py install.sh 2>/dev/null || true
chmod +x cpp/build.sh cpp/snck_ultra.sh 2>/dev/null || true

open_firewall

echo "[*] self-check..."
python -c "from web.app import app; print('[ok] web.app import')" || {
  echo "[!] import failed"
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
