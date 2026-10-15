#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
g++ -O3 -march=native -pthread -std=c++17 -o snck_l4 snck_l4.cpp
chmod +x snck_l4 2>/dev/null || true
echo "[\u2713] built $(pwd)/snck_l4"
ls -la snck_l4
