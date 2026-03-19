# Analyse_IA
Autonomous AI Data Analyst , powered by Mistral - RGPD Compliant

## Local Full Stack (Docker Compose)

See `DOCKER_COMPOSE_FULLSTACK.md` for one-command local deployment (backend + worker + frontend + postgres + redis + ollama).

## CI/CD (Task 17)

GitHub Actions workflow: `.github/workflows/ci-cd.yml`

Includes:
- Backend tests + syntax/lint checks
- Frontend lint + build
- Python dependency security scan (`pip-audit`)
- Lightweight performance smoke benchmark
- Optional Railway deploy on `main`

Optional deploy secrets:
- `RAILWAY_TOKEN`
- `RAILWAY_SERVICE`
