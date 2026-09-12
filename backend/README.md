# InvestFlow Backend

FastAPI backend for InvestFlow property management.

**Tabular store:** Azure Postgres (`app` schema) via `USE_POSTGRES_STORE=true`.  
**Blobs:** Azure Data Lake (`investflowadls`). Lakekeeper/Iceberg has been removed.

## Local Docker (recommended)

```bash
cd backend
cp env.example .env   # if needed; fill POSTGRES_* + AZURE_STORAGE_*
docker compose up --build
```

| Service  | URL                    |
|----------|------------------------|
| Backend  | http://localhost:8000  |
| Frontend | http://localhost:3000  |
| API docs | http://localhost:8000/docs |

Compose loads `backend/.env`, mounts `./app` into the backend for code changes, and runs the frontend with `npm run dev` (hot reload).

Health check:

```bash
curl -s http://localhost:8000/api/v1/health
```

Write smoke (against the DB in `.env`):

```bash
USE_POSTGRES_STORE=true uv run python -m app.scripts.smoke_postgres_writes
```

## Direct (no Docker)

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Production deploy

Push to `main` → GitHub Actions workflow `.github/workflows/deploy.yml` builds and updates:

- `investflow-backend`
- `investflow-frontend`

See `docs/migration/ICEBERG_TO_POSTGRES_CYCLE.md` for the completed Iceberg → Postgres migration notes.

## Project structure

```
backend/
├── app/
│   ├── api/          # API endpoints
│   ├── core/         # config, postgres_store, iceberg helpers (Postgres-only)
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── scripts/      # export_postgres_to_adls, smoke_postgres_writes, …
├── docker-compose.yml
├── Dockerfile
└── env.example
```
