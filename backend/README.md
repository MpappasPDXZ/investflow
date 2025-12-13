# InvestFlow Backend

FastAPI backend for InvestFlow property management system.

## ⚠️ CRITICAL: Local vs Production Data

### Architecture Overview

```
LOCAL DEVELOPMENT                     PRODUCTION (AZURE)
─────────────────                     ──────────────────
Docker Container                      Azure Container App
       │                                     │
       ▼                                     ▼
Local Lakekeeper                      Azure Lakekeeper
(http://lakekeeper:8181)              (https://investflow-lakekeeper.*.azurecontainerapps.io)
       │                                     │
       ▼                                     ▼
Local PostgreSQL                      Azure PostgreSQL
(Docker container)                    (if-postgres.postgres.database.azure.com)
       │                                     │
       ▼                                     ▼
Local filesystem                      Azure Data Lake (ADLS)
(/tmp/iceberg-data)                   (investflowadls)
```

### 🚨 HOW TO RUN SCRIPTS CORRECTLY

| Command | Target | When to Use |
|---------|--------|-------------|
| `docker-compose exec backend python -m app.scripts.xxx` | **LOCAL** Lakekeeper | Testing locally only |
| `uv run python -m app.scripts.xxx` | **PRODUCTION** Azure | Uploading real data |

**NEVER use `docker-compose exec` for production data!** It connects to the local Lakekeeper container, not Azure.

### Schema Must Match

Both local and production use the **same Iceberg table schemas**. When you add columns:

1. Update the schema in `app/api/` or `app/schemas/`
2. Update ALL upload scripts to include new columns
3. Deploy backend to Azure (GitHub Actions auto-deploys on push to `main`)
4. Run upload scripts with `uv run` for production

### Example: Uploading Data to Production

```bash
# ✅ CORRECT - Uses .env with Azure credentials
cd backend
uv run python -m app.scripts.upload_comparables

# ❌ WRONG - Uses local Docker Lakekeeper
docker-compose exec backend python -m app.scripts.upload_comparables
```

### Deployment Checklist

After adding new API endpoints or schemas:

1. ✅ Push code to `main` branch
2. ✅ Wait for GitHub Actions "Deploy to Azure" to complete
3. ✅ Verify endpoint exists: `curl https://investflow-backend.*.azurecontainerapps.io/api/v1/YOUR_ENDPOINT`
4. ✅ Run data scripts with `uv run` (not docker-compose exec)

---

## Quick Start

### 1. Install Dependencies

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 2. Configure Environment

```bash
cp env.example .env
# Edit .env with your Azure credentials for PRODUCTION access
```

### 3. Start Local Development Stack

```bash
docker-compose up -d
```

This starts:
- `lakekeeper` - Local Iceberg catalog (port 8181)
- `backend` - FastAPI server (port 8000)
- `frontend` - Next.js app (port 3000)

### 4. Start FastAPI Server (Alternative - Direct)

```bash
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Project Structure

```
backend/
├── app/
│   ├── api/          # API endpoints (add new routers here)
│   ├── core/         # Core configuration & Iceberg helpers
│   ├── models/       # Data models
│   ├── schemas/      # Pydantic schemas (validation)
│   ├── services/     # Business logic
│   └── scripts/      # Data upload scripts (use uv run for prod!)
└── docker-compose.yml
```

## Data Flow

```
API Request → FastAPI → Iceberg (via Lakekeeper) → ADLS (production) / Local files (dev)
```

The same code connects to different backends based on environment variables in `.env`.
