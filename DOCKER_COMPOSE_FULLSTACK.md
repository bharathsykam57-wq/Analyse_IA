# Docker Compose Full Stack (Task 16)

This setup runs Analyse_IA with one command, including:
- FastAPI backend
- Celery worker
- Next.js frontend
- PostgreSQL
- Redis
- Ollama

## 1) Prepare env

```bash
cp .env.docker.example .env.docker
```

Optionally edit values in `.env.docker`.

## 2) Start everything (one command)

```bash
docker compose --env-file .env.docker up -d --build
```

## 3) Verify services

```bash
docker compose ps
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
```

Frontend:
- http://localhost:3000

Backend API docs (dev only):
- http://localhost:8000/docs

## 4) Pull Ollama model (optional)

```bash
docker exec -it analyseia-ollama ollama pull mistral-nemo
```

If you prefer Groq or another provider, set in `.env.docker`:
- `LLM_PROVIDER=groq`
- `OLLAMA_REQUIRED=false`

## 5) Logs

```bash
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f frontend
```

## 6) Stop and cleanup

```bash
docker compose down
```

Remove volumes too:

```bash
docker compose down -v
```

## Notes

- `migrate` service runs `alembic upgrade head` automatically before backend starts.
- Uploaded files persist in `uploads_data` volume.
- DB/Redis/Ollama data are persisted in named volumes.
