#!/usr/bin/env bash
# One-command end-to-end demo.
#
# Starts the x402 facilitator and the paid server, waits for them to be ready,
# then runs the autonomous paying agent against /data so you can watch a full
# pay -> settle -> record cycle.
#
# Prerequisites:
#   - scripts/deploy.py has been run (TUSD/LEDGER/PAY_TO addresses in .env)
#   - the wallet is funded with testnet PHRS for gas
#
# TESTNET ONLY.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"
[ -x ".venv/bin/python" ] && PY=".venv/bin/python"

FAC_URL="${FACILITATOR_URL:-http://127.0.0.1:8401}"
SRV_URL="${SERVER_URL:-http://127.0.0.1:8402}"

cleanup() {
  [ -n "${FAC_PID:-}" ] && kill "$FAC_PID" 2>/dev/null || true
  [ -n "${SRV_PID:-}" ] && kill "$SRV_PID" 2>/dev/null || true
}
trap cleanup EXIT

wait_up() {  # $1 = url to probe
  for _ in $(seq 1 40); do
    curl -s -o /dev/null "$1" && return 0
    sleep 0.5
  done
  echo "Timed out waiting for $1" >&2
  return 1
}

echo "Starting facilitator ..."
"$PY" scripts/facilitator.py >/tmp/x402_facilitator.log 2>&1 &
FAC_PID=$!

echo "Starting paid server ..."
"$PY" scripts/server.py >/tmp/x402_server.log 2>&1 &
SRV_PID=$!

wait_up "$FAC_URL/supported"
wait_up "$SRV_URL/data"
echo "Both services are up."

echo
echo "=== Running autonomous paying agent ==="
"$PY" scripts/agent_pay.py /data

echo
echo "Done. Service logs: /tmp/x402_facilitator.log  /tmp/x402_server.log"
