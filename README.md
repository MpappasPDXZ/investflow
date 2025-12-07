# InvestFlow

Rental Property Management & Cash Flow Analysis Platform

## Overview

InvestFlow is a comprehensive application for managing rental properties, tracking expenses, analyzing cash flow scenarios, and maintaining CPA-ready bookkeeping records.

## Architecture

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Next.js 14 with React and TypeScript
- **Data Lake**: Apache Iceberg with Lakekeeper (REST catalog)
- **Storage**: Azure Data Lake Storage Gen2 (ADLS)
- **Deployment**: Azure Container Apps
- **Monorepo**: Single repository for backend and frontend

### Authentication & Data Flow

#### Frontend → Backend → Lakekeeper

1. **User Authentication**
   - Frontend sends credentials to `/api/v1/auth/login`
   - Backend validates against **ADLS Auth Cache** (parquet file)
   - Returns JWT token with `user_id` and `email`
   - Frontend stores token and uses in `Authorization: Bearer {token}` header

2. **Auth Cache Service (ADLS Parquet)**
   - **Location**: `documents/cdc/users/users_current.parquet`
   - **Purpose**: O(1) user lookups without scanning Iceberg tables
   - **Updates**: Inline CDC - cache updates immediately when users are created/modified
   - **Benefits**: Sub-millisecond authentication, no database load

3. **Data Access Pattern**
   ```
   Frontend (Next.js)
     ↓ HTTP/REST + JWT
   Backend (FastAPI)
     ↓ Check Auth Cache (ADLS parquet)
     ↓ Query Data (PyIceberg)
   Lakekeeper (Iceberg Catalog)
     ↓ Metadata + Location
   ADLS (Data Files)
   ```

4. **Property Sharing**
   - Shares cached in: `documents/cdc/shares/user_shares_current.parquet`
   - Bidirectional sharing resolved via cache lookups
   - Properties filtered by owner OR shared access

5. **Testing Environment**
   - Local frontend (`localhost:3000`) → Local backend (`localhost:8000`)
   - Local backend → Local Lakekeeper (`localhost:8181`)
   - Both local AND Azure share same ADLS storage
   - Both local AND Azure share same PostgreSQL database (for Lakekeeper metadata)
   - **Important**: Changes made locally appear in Azure and vice versa

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
admin login to the application:
email: "matt.pappasemail@kiewit.com"
password: levi0210

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
### Backend Setup && Frontend Setup
# only run from Docker
cd /Users/matt/code/property/backend
docker-compose down
docker-compose up --build -d

### POSTGRES SETUP
POSTGRES_HOST=if-postgres.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=if-postgres
POSTGRES_USER=pgadmin
POSTGRES_PASSWORD=pass1234!


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
- Storage Account: `investflowadls` (ADLS Gen2)
- Container Registry: `investflowregistry`
- Container Apps Environment: `investflow-env`
- Key Vault: `investflow-kv`
- Application Insights: `investflow-insights`

## Current Status (Dec 7, 2025)

### Git Revert Completed
- Reverted to commit `e6e5493` (Fix Cash on Cash Return formula)
- All reverted code changes are in Git
- Migration scripts were removed in the revert

### Database Status
✅ **PostgreSQL**: Clean and migrated
- Lakekeeper schema successfully created
- All tables and types cleaned and recreated

✅ **ADLS Data**: Safe and intact
- All property, expense, rent, and user data preserved
- Auth cache exists: `documents/cdc/users/users_current.parquet`
- Shares cache exists: `documents/cdc/shares/user_shares_current.parquet`

### Container Status
✅ Lakekeeper: Running on port 8181
✅ Frontend: Running on port 3000
❌ Backend: Crashing - needs warehouse configured

### Next Steps to Restore Data Access

**Issue**: Lakekeeper requires OAuth2 authentication before warehouse can be created.

**Required Environment Variables** (need to be set in `.env`):
```bash
# Backend OAuth2 for Lakekeeper Authentication
LAKEKEEPER__OAUTH2__CLIENT_ID=<Azure AD App Client ID>
LAKEKEEPER__OAUTH2__CLIENT_SECRET=<Azure AD App Secret>
LAKEKEEPER__OAUTH2__TENANT_ID=<Azure AD Tenant ID>
LAKEKEEPER__OAUTH2__SCOPE=api://lakekeeper/.default

# Lakekeeper OpenID Configuration
LAKEKEEPER__OPENID_PROVIDER_URI=https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration
LAKEKEEPER__OPENID_AUDIENCE=api://lakekeeper
```

**Once Auth is Configured**:
1. Restart containers: `docker-compose restart`
2. Backend will authenticate via OAuth2
3. Create/restore warehouse via Lakekeeper management API
4. All Iceberg tables in ADLS will be accessible

**Alternative**: Use Azure production instance - it should still be working with existing auth.
