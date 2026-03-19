# Analyse_IA
Autonomous AI Data Analyst , powered by Mistral - RGPD Compliant

## Local Full Stack (Docker Compose)

See `DOCKER_COMPOSE_FULLSTACK.md` for one-command local deployment (backend + worker + frontend + postgres + redis + ollama).

## CI/CD (Task 17)

GitHub Actions workflow: `.github/workflows/ci-cd.yml`

Manual deploy workflow: `.github/workflows/deploy-railway.yml`

Includes:
- Backend tests + syntax/lint checks
- Frontend lint + build
- Python dependency security scan (`pip-audit`)
- Lightweight performance smoke benchmark
- Optional manual Railway deploy (workflow dispatch)

Manual deploy inputs (workflow dispatch):
- `railway_token`
- `railway_service`
