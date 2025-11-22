# InvestFlow

Rental Property Management & Cash Flow Analysis Platform

## Overview

InvestFlow is a comprehensive application for managing rental properties, tracking expenses, analyzing cash flow scenarios, and maintaining CPA-ready bookkeeping records.

## Architecture

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Next.js 14 with React and TypeScript
- **Database**: Apache Iceberg with Nessie REST Catalog
- **Storage**: Azure Blob Storage
- **Deployment**: Azure Container Apps
- **Monorepo**: Single repository for backend and frontend

## Project Structure

```
investflow/
├── backend/          # FastAPI application
│   ├── app/         # Application code
│   ├── tests/       # Test files
│   └── pyproject.toml
├── frontend/         # Next.js application
│   ├── app/         # Next.js app directory
│   ├── components/  # React components
│   └── package.json
├── azure-resources.md  # Azure infrastructure documentation
└── make_app.txt     # Complete application specification
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Azure CLI
- Docker (for containerization)

### Backend Setup

```bash
cd backend
# Install UV (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your values

# Run the application
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your values

# Run the development server
npm run dev
```

## Development

See individual README files in `backend/` and `frontend/` directories for detailed setup instructions.

## Azure Infrastructure

All Azure resources are documented in `azure-resources.md`. The infrastructure includes:

- Resource Group: `investflow-rg`
- Storage Account: `investflowstorage`
- Container Registry: `investflowregistry`
- Container Apps Environment: `investflow-env`
- Key Vault: `investflow-kv`
- Application Insights: `investflow-insights`

## License

[To be determined]

