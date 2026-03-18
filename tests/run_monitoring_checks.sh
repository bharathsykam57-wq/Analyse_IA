#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
BACKEND_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-url)
      BACKEND_URL="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--backend-url https://analyseiabackend-production.up.railway.app]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python executable not found: $PYTHON_BIN"
  echo "Set PYTHON_BIN explicitly, e.g. PYTHON_BIN=$(which python3) $0"
  exit 1
fi

echo "============================================================"
echo "MONITORING CHECKS"
echo "Root: $ROOT_DIR"
echo "Python: $PYTHON_BIN"
if [[ -n "$BACKEND_URL" ]]; then
  echo "Backend URL: $BACKEND_URL"
else
  echo "Backend URL: (local testclient only)"
fi
echo "============================================================"

echo
echo "[RUN] Local monitoring metrics smoke"
"$PYTHON_BIN" "$ROOT_DIR/tests/test_monitoring_metrics.py"
echo "[PASS] Local monitoring metrics smoke"

echo
echo "[RUN] MLOps bootstrap smoke"
"$PYTHON_BIN" "$ROOT_DIR/tests/test_mlops_bootstrap.py"
echo "[PASS] MLOps bootstrap smoke"

if [[ -n "$BACKEND_URL" ]]; then
  echo
  echo "[RUN] Remote /api/v1/metrics endpoint check"
  METRICS_OUTPUT="$(curl -sS "$BACKEND_URL/api/v1/metrics")"
  if [[ "$METRICS_OUTPUT" != *"analyseia_http_requests_total"* ]]; then
    echo "[FAIL] Remote metrics output missing analyseia_http_requests_total"
    exit 1
  fi
  if [[ "$METRICS_OUTPUT" != *"analyseia_celery_task_events_total"* ]]; then
    echo "[FAIL] Remote metrics output missing analyseia_celery_task_events_total"
    exit 1
  fi
  echo "[PASS] Remote /api/v1/metrics endpoint check"
fi

echo
echo "============================================================"
echo "ALL SELECTED MONITORING CHECKS PASSED"
echo "============================================================"
