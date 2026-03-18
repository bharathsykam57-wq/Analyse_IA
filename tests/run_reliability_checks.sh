#!/usr/bin/env bash
set -euo pipefail

# Reliability regression runner for Celery/WebSocket/Webhook/DLQ hardening.
#
# Usage:
#   ./tests/run_reliability_checks.sh
#   ./tests/run_reliability_checks.sh --production-url https://your-backend
#
# Optional env vars:
#   PYTHON_BIN=/path/to/python

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
PRODUCTION_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --production-url)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --production-url requires a value"
        exit 1
      fi
      PRODUCTION_URL="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--production-url <url>]"
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python executable not found or not executable: $PYTHON_BIN"
  echo "Set PYTHON_BIN explicitly, e.g.: PYTHON_BIN=$(which python3) $0"
  exit 1
fi

echo "============================================================"
echo "RELIABILITY CHECKS"
echo "Root: $ROOT_DIR"
echo "Python: $PYTHON_BIN"
if [[ -n "$PRODUCTION_URL" ]]; then
  echo "Production URL: $PRODUCTION_URL"
else
  echo "Production URL: (not set)"
fi
echo "============================================================"

run_test() {
  local label="$1"
  shift
  echo
  echo "[RUN] $label"
  if "$@"; then
    echo "[PASS] $label"
  else
    echo "[FAIL] $label"
    return 1
  fi
}

# Local deterministic checks (no external deps)
run_test "Webhook delivery resilience" \
  "$PYTHON_BIN" "$ROOT_DIR/tests/test_task_webhook_delivery.py"

run_test "Webhook payload schema" \
  "$PYTHON_BIN" "$ROOT_DIR/tests/test_task_webhook_schema.py"

run_test "Ops DLQ endpoint behavior" \
  "$PYTHON_BIN" "$ROOT_DIR/tests/test_ops_dlq_endpoint.py"

# Optional production queue smoke
if [[ -n "$PRODUCTION_URL" ]]; then
  run_test "Production Celery queue smoke" \
    "$PYTHON_BIN" "$ROOT_DIR/tests/test_production_celery.py" --backend-url "$PRODUCTION_URL"
fi

echo
echo "============================================================"
echo "ALL SELECTED RELIABILITY CHECKS PASSED"
echo "============================================================"
