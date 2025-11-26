# InvestFlow Backend

FastAPI backend for InvestFlow property management system.

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
# Edit .env and set required variables
```

### 3. Start Gravitino

```bash
docker-compose up -d gravitino
```

### 4. Initialize Catalog (if needed)

```bash
uv run app/scripts/init_fileset_catalog.py
```

### 5. Start FastAPI Server

```bash
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Project Structure

```
backend/
├── app/
│   ├── api/          # API endpoints
│   ├── core/         # Core configuration
│   ├── models/       # Data models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic
│   └── scripts/      # Utility scripts
└── docker-compose.yml
```
