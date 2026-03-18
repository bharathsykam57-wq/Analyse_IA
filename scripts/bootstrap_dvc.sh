#!/usr/bin/env bash
set -euo pipefail

# Bootstrap DVC dataset versioning for Analyse_IA.
#
# Usage:
#   ./scripts/bootstrap_dvc.sh --dry-run
#   DVC_REMOTE_URL=s3://my-bucket/analyseia-dvc ./scripts/bootstrap_dvc.sh
#
# Optional env vars:
#   DVC_REMOTE_NAME (default: storage)
#   DVC_REMOTE_URL  (required to configure remote automatically)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--dry-run]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

run_cmd() {
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] $*"
  else
    eval "$@"
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command '$cmd' is not installed"
    return 1
  fi
  return 0
}

echo "============================================================"
echo "DVC BOOTSTRAP"
echo "Root: $ROOT_DIR"
echo "Dry-run: $DRY_RUN"
echo "============================================================"

if [[ "$DRY_RUN" != "true" ]]; then
  require_cmd dvc
fi

cd "$ROOT_DIR"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[INFO] Skipping tool existence checks in dry-run mode"
fi

# Initialize DVC if needed.
if [[ -d .dvc ]]; then
  echo "[INFO] .dvc already exists, skipping dvc init"
else
  run_cmd "dvc init"
fi

# Configure optional remote.
DVC_REMOTE_NAME="${DVC_REMOTE_NAME:-storage}"
if [[ -n "${DVC_REMOTE_URL:-}" ]]; then
  run_cmd "dvc remote add -d $DVC_REMOTE_NAME $DVC_REMOTE_URL"
  run_cmd "dvc remote default $DVC_REMOTE_NAME"
else
  echo "[INFO] DVC_REMOTE_URL not set, remote setup skipped"
fi

# Track runtime data directories.
for target in data/raw data/processed data/pdfs; do
  if [[ -e "$target" ]]; then
    run_cmd "dvc add $target"
  else
    echo "[INFO] Missing target '$target', skipped"
  fi
done

# Suggest commit set.
echo
echo "Next steps:"
echo "  1) Review generated .dvc files"
echo "  2) git add .dvc .dvc/config* data/**/*.dvc"
echo "  3) git commit -m 'chore: bootstrap DVC dataset tracking'"
echo "  4) dvc push (after remote is configured)"

echo
echo "PASS: DVC bootstrap completed"
