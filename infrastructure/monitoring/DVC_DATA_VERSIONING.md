# DVC Dataset Versioning (Task 11)

This project now includes a bootstrap script for dataset version tracking:

- Script: `scripts/bootstrap_dvc.sh`
- Purpose: initialize DVC, optionally configure remote storage, and track `data/raw`, `data/processed`, `data/pdfs`

## Quick Start

```bash
# Preview actions safely
./scripts/bootstrap_dvc.sh --dry-run

# Run for real (with remote)
DVC_REMOTE_URL=s3://your-bucket/analyseia-dvc ./scripts/bootstrap_dvc.sh
```

## Recommended Remote Backends

- S3 / MinIO
- Azure Blob
- GCS
- SSH filesystem

## Daily Workflow

```bash
# Update data files
# ...

# Refresh tracking
dvc add data/raw data/processed data/pdfs

# Commit metadata
git add data/**/*.dvc dvc.lock dvc.yaml .dvc/config
git commit -m "chore(data): update tracked datasets"

# Push data artifacts
dvc push
```

## Notes

- `data/` is git-ignored in this repo, so only DVC metadata should be committed.
- For CI/CD, pull data via `dvc pull` before running training/evaluation.
