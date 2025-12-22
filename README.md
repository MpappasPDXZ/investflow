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

## Lakekeeper & PostgreSQL Authentication

### ⚠️ CRITICAL: Encryption Key Must Match

**If production breaks after `git push` but local works, check the encryption key first.**

**The Problem:**
- Local and production Lakekeeper share the same PostgreSQL database
- Warehouse storage credentials are encrypted with `LAKEKEEPER__PG_ENCRYPTION_KEY`
- If keys don't match → production can't decrypt → "SecretFetchError: Wrong key or corrupt data"
- **Result**: Production returns no data, even though data exists in ADLS

**Quick Fix:**
```bash
# 1. Check if keys match
LOCAL_KEY=$(grep "^LAKEKEEPER__PG_ENCRYPTION_KEY=" backend/.env | cut -d'=' -f2- | xargs)
PROD_KEY=$(az containerapp show --name investflow-lakekeeper --resource-group investflow-rg \
  --query "properties.template.containers[0].env[?name=='LAKEKEEPER__PG_ENCRYPTION_KEY'].value" -o tsv)

# 2. If they don't match, fix it
if [ "$LOCAL_KEY" != "$PROD_KEY" ]; then
  ./fix_production_encryption_key.sh
fi
```

**Prevention (Automatic via Git):**

- **`deploy.sh`**: Automatically reads from `backend/.env` and sets production to match
- **GitHub Actions**: Uses `LAKEKEEPER_ENCRYPTION_KEY` secret (must match `backend/.env`)

**Set GitHub Secret (one-time):**
```bash
# Get your local key
grep LAKEKEEPER__PG_ENCRYPTION_KEY backend/.env

# Add to GitHub: Settings → Secrets → Actions → New secret
# Name: LAKEKEEPER_ENCRYPTION_KEY
# Value: <paste from backend/.env>
```

### Lakekeeper Configuration

**Required Environment Variables:**

**Lakekeeper Container App:**
```bash
# PostgreSQL connection (shared with local)
LAKEKEEPER__PG_DATABASE_URL_READ=postgresql://pgadmin:pass1234!@if-postgres.postgres.database.azure.com:5432/if-postgres?sslmode=require
LAKEKEEPER__PG_DATABASE_URL_WRITE=postgresql://pgadmin:pass1234!@if-postgres.postgres.database.azure.com:5432/if-postgres?sslmode=require

# Encryption key (MUST match local backend/.env)
LAKEKEEPER__PG_ENCRYPTION_KEY=<same-as-local>

# Azure storage access
LAKEKEEPER__ENABLE_AZURE_SYSTEM_CREDENTIALS=false
AZURE_STORAGE_ACCOUNT_NAME=investflowadls
AZURE_STORAGE_ACCOUNT_KEY=<storage-key>
```

**Backend Container App:**
```bash
# Lakekeeper connection
LAKEKEEPER__BASE_URI=https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io
LAKEKEEPER__WAREHOUSE_NAME=lakekeeper

# OAuth2 for backend → Lakekeeper (works automatically, no issues to date)
LAKEKEEPER__OAUTH2__CLIENT_ID=2f43977e-7c3d-478f-86b0-f72b82e869dd
LAKEKEEPER__OAUTH2__CLIENT_SECRET=<secret>
LAKEKEEPER__OAUTH2__TENANT_ID=479bc30b-030f-4a2e-8ea2-67f549b32f5e
LAKEKEEPER__OAUTH2__SCOPE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default
```

**All of these are set automatically by:**
- `deploy.sh` (reads from `backend/.env`)
- GitHub Actions workflow (uses GitHub Secrets)

### Troubleshooting

**Production broken after git push, but local works?**
1. Check encryption key: `./fix_production_encryption_key.sh`
2. Check Lakekeeper health: `curl https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io/health`
3. Check backend logs: `az containerapp logs show --name investflow-backend --resource-group investflow-rg --tail 50`

**"SecretFetchError: Wrong key or corrupt data"**
→ Encryption key mismatch. Run `./fix_production_encryption_key.sh`

**"No data returned" but data exists in ADLS**
→ Lakekeeper can't access ADLS. Check `AZURE_STORAGE_ACCOUNT_KEY` is set in Lakekeeper container app.

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

## Leasing Workflow (Tenant Onboarding)

InvestFlow provides a complete tenant onboarding workflow, from initial application through move-in. This system is designed for landlords to manage the entire leasing process after a prospective tenant has toured the property.

### Complete Workflow (7 Steps)

1. **Background Check** - Screen prospective tenants
2. **Rental Application** - Download Nebraska/Missouri application forms to send to tenants
3. **Create Lease** - Generate state-compliant lease agreements (see Lease Generation System below)
4. **View Leases** - Review all executed leases
5. **Deposits & Fees** - Log security deposits, pet fees, and first month rent payments
6. **Property Walkthrough** - Document property condition with photos and notes
7. **Exit Checklist** - Prepare tenants for move-out requirements

### Rental Application Forms

#### Available Forms
- **Nebraska Residential Rental Application** (PDF, 575KB)
- **Missouri Residential Rental Application** (PDF, 179KB - auto-generated from HTML)

#### Workflow
1. Landlord downloads blank application form from `/leasing/application`
2. Sends PDF to prospective tenant via email or text
3. Tenant completes and returns application
4. Landlord uploads completed application to Vault for record-keeping
5. Application is tagged with property address and tenant name

#### Generating New Forms
```bash
cd frontend
npm run generate-pdfs
```

This uses Puppeteer to convert HTML templates in `/frontend/public/` to professional PDF forms. See `/frontend/scripts/README.md` for details on adding new state forms.

## Lease Generation System

InvestFlow includes a comprehensive lease generation system for creating state-compliant residential lease agreements. All files are stored in ADLS, ensuring consistency between local and production environments.

### Architecture

```
User Form Data
    ↓
Backend API → Apply State Defaults (NE/MO)
    ↓
Store in Iceberg Tables → investflow.leases + investflow.lease_tenants
    ↓
Generate LaTeX Document → Template-based with dynamic data
    ↓
Compile to PDF (TinyTeX) → Local /tmp/ compilation only
    ↓
Save to ADLS → documents/leases/generated/{user_id}/{lease_id}/
    ↓
Return Signed URL → Frontend displays/downloads PDF
```

### Database Schema

#### `investflow.leases` Table
Stores complete lease terms with 90+ fields covering:
- **Financial Terms**: rent, security deposit, late fees, NSF fees
- **Dates**: commencement, termination, lease date
- **Occupancy**: max occupants, adults, children allowed
- **Pets**: allowed, fees, max count
- **Utilities**: tenant-paid vs landlord-paid
- **Property Features**: parking, keys, shared driveway, garage, attic, basement
- **State-Specific**: deposit return days, disclosure requirements
- **Move-out Costs**: JSON array of dynamic cleaning/repair fees
- **Documents**: generated PDF blob name, template version

#### `investflow.lease_tenants` Table
Stores tenant information for each lease:
- Multiple tenants per lease (joint and several liability)
- Tenant order, names, contact info
- Signature dates

### ADLS Storage Structure

```
documents/  (ADLS container)
├── leases/
│   └── generated/
│       └── {user_id}/
│           └── {lease_id}/
│               ├── lease_316_S_50th_Ave_20251214_084830.pdf
│               └── lease_316_S_50th_Ave_20251214_084830.tex
├── expenses/
│   └── {user_id}/  # Receipt uploads
└── user_documents/
    └── {user_id}/  # Other document uploads
```

**Why ADLS for Everything?**
- Local and production share the same ADLS account
- Files created locally are immediately available in production
- No sync issues or deployment steps for documents
- Automatic backup and geo-redundancy
- Audit trail via blob metadata

### State-Specific Rules

| Feature | Nebraska (NE) | Missouri (MO) |
|---------|---------------|---------------|
| **Max Security Deposit** | 1 month's rent | 2 months' rent |
| **Deposit Return** | 14 days | 30 days |
| **Late Fee Structure** | Progressive: $75→$150→$225 | Must be "reasonable" |
| **Methamphetamine Disclosure** | Not required | **Required** |
| **Move-out Inspection Rights** | Not required | **Required** |
| **Military Termination** | Not specified | 30 days notice |

### PDF Generation Process

1. **Template Engine**: LaTeX-based for professional formatting
2. **TinyTeX**: Lightweight TeX distribution installed in Docker container
3. **Dynamic Content**: Property details, tenant names, financial terms
4. **Compilation**: Runs in local `/tmp/` (auto-cleaned after compilation)
5. **Final Storage**: PDF + LaTeX source saved to ADLS with metadata

### Key Services

#### `lease_defaults.py`
- Centralized default values for all lease fields
- State-specific overrides (NE vs MO)
- Default move-out cost schedules
- Early termination fee calculations

#### `lease_generator_service.py`
- Builds LaTeX document from lease data
- Compiles PDF using `pdflatex`
- Saves both PDF and LaTeX source to ADLS
- Returns blob names for database storage

#### `adls_service.py`
- Upload/download blobs to ADLS
- Generate time-limited SAS URLs for secure downloads
- Manage blob metadata and access control

### Template Structure

Leases follow the `NE_res_agreement.tex` template with 39 sections:

1. Premises (property description)
2. Lease Term (dates)
3. Rent (amount, due dates, prorated)
4. Late Charges (progressive fees)
5. Insufficient Funds (NSF fee)
6. Security Deposit (amount, return period)
7-13. Standard clauses (defaults, possession, use, occupancy, etc.)
14. Dangerous Materials
15. Utilities (tenant vs landlord responsibilities)
16. Pets (fees, restrictions)
17-18. Alterations and damage
19. Maintenance and Repair (including shared driveway, snow removal)
20-32. Standard legal clauses (inspection, abandonment, insurance, governing law, etc.)
33. Parking (spaces, vehicle size limits)
34. Keys (quantity, replacement fees)
35-37. Liquid furniture, indemnification, legal fees
38. Additional Terms (appliances, attic, lead paint, early termination, garage)
39. Move-out Cost Schedule (dynamic JSON array)

### Docker Configuration

Backend Dockerfile includes TinyTeX for PDF generation:

```dockerfile
RUN apt-get update && apt-get install -y \
    gcc g++ wget perl curl \
    && wget -qO- "https://yihui.org/tinytex/install-bin-unix.sh" | sh \
    && /root/bin/tlmgr install enumitem titlesec fancyhdr tabularx

ENV PATH="/root/bin:$PATH"
```

### Testing

**Upload Sample Lease (316 S 50th Ave):**
```bash
cd backend
uv run app/scripts/upload_316_lease.py
```

**Compare Generated Output to Template:**
```bash
uv run app/scripts/compare_lease_output.py
```

### Running Schema Migrations

When new fields are added to existing tables or new tables are created, you need to run migration scripts.

**⚠️ Important:** Migration scripts MUST be run inside the backend container to access:
- Lakekeeper OAuth2 credentials (for catalog operations)
- ADLS credentials (for reading/writing parquet files)
- PostgreSQL connection (via Lakekeeper)
- Proper network access to all services

**Run Migration (Inside Container):**
```bash
# From your host machine
cd backend
docker-compose exec backend uv run app/scripts/migrate_add_fields.py
```

**Or if container is not running:**
```bash
# Start containers first
docker-compose up -d

# Then run migration
docker-compose exec backend uv run app/scripts/migrate_add_fields.py
```

**Migration Script Features:**
- ✅ Preserves all existing data
- ✅ Adds new columns with NULL values
- ✅ Creates new tables if they don't exist
- ✅ Uses Iceberg schema evolution (no downtime)
- ✅ Idempotent (safe to run multiple times)

**Example Migration Output:**
```
🚀 Starting schema migration...
🔄 Migrating properties table...
  ➕ Adding cash_invested column
  ✅ Properties table migrated successfully
🔄 Migrating leases table...
  ➕ Adding pet_deposit_total column
  ➕ Adding pet_description column
  ✅ Leases table migrated successfully
🔄 Creating walkthrough tables...
  ➕ Creating walkthroughs table
  ✅ Walkthroughs table created
  ➕ Creating walkthrough_areas table
  ✅ Walkthrough_areas table created
✅ Migration completed successfully!
```

**Why Run in Container?**

The backend container has access to:
1. **OAuth2 Credentials**: `LAKEKEEPER__OAUTH2__CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`
2. **ADLS Credentials**: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY`
3. **Network Access**: Can reach Lakekeeper (port 8181) and PostgreSQL (Azure)
4. **Python Environment**: All dependencies installed via UV

Running outside the container would require manually setting all environment variables and ensuring network connectivity.

**Verify Migration Success:**
```bash
# Check Lakekeeper catalog
curl -s http://localhost:8181/catalog/v1/investflow/namespaces/investflow/tables | jq

# Check backend logs
docker-compose logs backend --tail=50

# Test in application
# Navigate to property details page, should see new "Cash Invested" field
```

**Rollback (if needed):**
See `backend/app/scripts/MIGRATION_README.md` for detailed rollback procedures using ADLS backups.

### Common Migration Mistakes

**❌ Mistake #1: Wrong Hook Signature**
```typescript
// WRONG - useExpenses only takes a string parameter
const { data: expensesData } = useExpenses({ property_id: id, limit: 10000 });

// CORRECT - pass propertyId as simple string
const { data: expensesData } = useExpenses(id);
```
**Error:** `Type error: Argument of type '{ property_id: string; limit: number; }' is not assignable to parameter of type 'string'.`

**❌ Mistake #2: Adding Columns Without Schema Update**
```python
# WRONG - Can't just add columns to DataFrame and overwrite
df["new_column"] = None
table.overwrite(arrow_table)  # Fails!

# CORRECT - Must update schema first
with table.update_schema() as update:
    update.add_column("new_column", DecimalType(12, 2), required=False)
```
**Error:** `PyArrow table contains more columns: new_column. Update the schema first (hint, use union_by_name).`

**Solution:** Always use Iceberg's schema evolution API (`table.update_schema()`) to add columns before writing data with those columns.

### Future Enhancements

- [ ] Frontend lease form with multi-step wizard
- [ ] Digital signature capture and storage
- [ ] Email PDF directly to tenants
- [ ] Lease renewal workflow
- [ ] Template library for different property types
- [ ] Version history and amendments

For detailed ADLS storage architecture, see `LEASE_GENERATION_ADLS.md`.

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

## Development Workflow

### Local Testing with Docker Compose

**Always test locally before deploying:**

```bash
cd backend
docker-compose down
docker-compose up --build -d
```

This starts all services locally:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Lakekeeper: http://localhost:8181

**Workflow:**
1. Make code changes
2. Test locally using `docker-compose`
3. **If schema changes**: Run migration script inside container (`docker-compose exec backend uv run app/scripts/migrate_add_fields.py`)
4. When ready, push to git
5. Deploy to Azure (see Deployment section below)

**Testing Locally:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Lakekeeper: http://localhost:8181

## Deployment

### Standard Deployment Process

**When you have new code changes to deploy:**

1. **Test locally first:**
```bash
cd backend
docker-compose up --build -d
# Test all changes, including any migrations
docker-compose exec backend uv run app/scripts/migrate_add_fields.py  # If schema changed
```

2. **Build and push new images to Azure Container Registry:**
```bash
# Build and push frontend
cd frontend
docker build --platform linux/amd64 -t investflowregistry.azurecr.io/investflow-frontend:latest .
az acr login --name investflowregistry
docker push investflowregistry.azurecr.io/investflow-frontend:latest

# Build and push backend
cd ../backend
docker build --platform linux/amd64 -t investflowregistry.azurecr.io/investflow-backend:latest .
docker push investflowregistry.azurecr.io/investflow-backend:latest
```

3. **Update Azure Container Apps to use the new images:**
```bash
# Update frontend only
az containerapp update --name investflow-frontend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-frontend:latest

# Update backend only
az containerapp update --name investflow-backend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-backend:latest

# Update both
az containerapp update --name investflow-frontend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-frontend:latest && \
az containerapp update --name investflow-backend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-backend:latest
```

4. **Run migrations in production (if schema changed):**
```bash
# Connect to Azure backend container and run migration
az containerapp exec \
  --name investflow-backend \
  --resource-group investflow-rg \
  --command "uv run app/scripts/migrate_add_fields.py"

# Or use Azure Container Apps console/logs to verify
az containerapp logs show \
  --name investflow-backend \
  --resource-group investflow-rg \
  --tail 100
```

**Important:** Schema migrations in production:
- ✅ Safe to run (Iceberg schema evolution preserves data)
- ✅ Idempotent (can run multiple times)
- ✅ Zero downtime (adds columns without locking)
- ⚠️ **Always test locally first!**
- ⚠️ **Backup before major schema changes:** `uv run backup_iceberg_tables.py`

### deploy.sh (Limited Use Case)

**⚠️ Important:** `deploy.sh` should **only** be used when container images are **NOT** being overwritten in Azure (e.g., initial setup, infrastructure changes, or when you want to deploy without building new images).

For normal code deployments, use the standard process above (build/push manually, then update container apps).

`deploy.sh` builds images and deploys everything, which is useful for:
- Initial infrastructure setup
- When you need to update container app configurations without code changes
- Full stack redeployment scenarios

**Not recommended for regular code deployments** - always test locally with `docker-compose` first, then use the manual build/push process.

**Automatic Encryption Key Sync:**
- `deploy.sh` automatically reads `LAKEKEEPER__PG_ENCRYPTION_KEY` from `backend/.env`
- Ensures production uses the same encryption key as local
- Prevents "SecretFetchError: Wrong key or corrupt data" issues
- **No manual intervention needed** - just ensure your local `.env` has the correct key

### POSTGRES SETUP
POSTGRES_HOST=if-postgres.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=if-postgres
POSTGRES_USER=pgadmin
POSTGRES_PASSWORD=pass1234!


# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your values


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
✅ Backend: Running on port 8000
- Connected to ADLS (investflowadls)
- Auth cache loaded: 5 users, 1 share
- Warehouse ID: 3a3b14be-d3ab-11f0-b3d2-67e9a9bacbb0

### Local Development Stack - Fully Operational ✅

**All services are running and connected to ADLS:**
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Lakekeeper: http://localhost:8181

**Data Access:**
- All services read/write to the same ADLS storage (investflowadls)
- Changes made locally are visible in Azure production and vice versa
- Auth cache loaded: 5 users, 1 share record
- Warehouse: `lakekeeper` (ID: 3a3b14be-d3ab-11f0-b3d2-67e9a9bacbb0)

### How to Recreate the Warehouse (If Needed)

If you need to reset Lakekeeper or the warehouse gets deleted:

#### Step 1: Verify OAuth2 Environment Variables

These should already be in your `.env` file:
```bash
# Backend OAuth2 for Lakekeeper Authentication
LAKEKEEPER__OAUTH2__CLIENT_ID=<Azure AD App Client ID>
LAKEKEEPER__OAUTH2__CLIENT_SECRET=<Azure AD App Secret>
LAKEKEEPER__OAUTH2__TENANT_ID=<Azure AD Tenant ID>
LAKEKEEPER__OAUTH2__SCOPE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default

# Lakekeeper OpenID Configuration
LAKEKEEPER__OPENID_PROVIDER_URI=https://login.microsoftonline.com/<TENANT_ID>/v2.0
LAKEKEEPER__OPENID_AUDIENCE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7
LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS=https://sts.windows.net/<TENANT_ID>/
```

#### Step 2: Create the Warehouse

**Important**: Lakekeeper must be running on port 8181 before running these commands.

```bash
# Get OAuth2 access token
TOKEN=$(curl -s -X POST \
  https://login.microsoftonline.com/${LAKEKEEPER__OAUTH2__TENANT_ID}/oauth2/v2.0/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=${LAKEKEEPER__OAUTH2__CLIENT_ID}" \
  -d "client_secret=${LAKEKEEPER__OAUTH2__CLIENT_SECRET}" \
  -d "scope=${LAKEKEEPER__OAUTH2__SCOPE}" \
  -d "grant_type=client_credentials" | jq -r .access_token)

# Create warehouse pointing to ADLS
curl -X POST http://localhost:8181/management/v1/warehouse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "warehouse-name": "lakekeeper",
    "project-id": "00000000-0000-0000-0000-000000000000",
    "storage-profile": {
      "type": "azdls",
      "account-name": "investflowadls",
      "filesystem": "documents"
    }
  }'
```

#### Step 3: Backend Auto-Restart

Once the warehouse is created:
1. Backend container will auto-restart (Docker restart policy)
2. Backend will authenticate via OAuth2 and connect to warehouse
3. All Iceberg tables in ADLS will be accessible
4. Local stack is now fully operational

#### Troubleshooting

**Check if warehouse exists**:
```bash
curl -s http://localhost:8181/management/v1/warehouse?project-id=00000000-0000-0000-0000-000000000000 \
  -H "Authorization: Bearer $TOKEN"
```

**View backend crash logs**:
```bash
cd backend
docker-compose logs backend --tail=50
```

## Architecture Deep Dive: Data Storage & Catalog

### Critical Concept: Metadata vs Data Separation

**Understanding this separation is critical to avoid data loss!**

InvestFlow uses Apache Iceberg, which separates metadata from data:

```
┌─────────────────────────────────────────────────────────────────┐
│                     METADATA LAYER                               │
│  PostgreSQL (via Lakekeeper)                                    │
│  - Table schemas                                                │
│  - Table locations (pointers to ADLS)                           │
│  - Snapshot history                                             │
│  - Partition information                                        │
│  └─ CAN BE LOST/RESET - but data remains safe!                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓ Points to
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
│  Azure Data Lake Storage (ADLS)                                 │
│  - Actual parquet files with your records                       │
│  - Immutable (never modified, only new files added)             │
│  - Survives catalog resets/deletions                            │
│  └─ YOUR DATA IS SAFE HERE FOREVER                              │
└─────────────────────────────────────────────────────────────────┘
```

### Backend's Dual Connection to ADLS

The backend accesses ADLS in **two different ways**:

#### 1. Via Iceberg/Lakekeeper (Structured Tables)
```python
# PyIceberg → Lakekeeper → PostgreSQL (metadata) → ADLS (data)
catalog = RestCatalog(uri="http://lakekeeper:8181/catalog")
table = catalog.load_table("investflow.expenses")
expenses = table.scan().to_pandas()  # Reads parquet from ADLS
```

**Tables accessed this way:**
- `investflow.expenses`
- `investflow.properties`
- `investflow.rents`
- `investflow.users`
- `investflow.clients`
- `investflow.scheduled_expenses`
- `investflow.scheduled_revenue`

**Flow:**
1. Backend queries Lakekeeper for table metadata
2. Lakekeeper checks PostgreSQL for file locations
3. Backend reads parquet files directly from ADLS
4. Data is returned to frontend

#### 2. Direct ADLS Access (Caches & Documents)
```python
# Direct Azure SDK → ADLS (no Lakekeeper involved)
from azure.storage.blob import BlobServiceClient
blob_client = BlobServiceClient(...)
data = blob_client.download_blob("documents/cdc/users/users_current.parquet")
```

**Files accessed this way:**
- `documents/cdc/users/users_current.parquet` (Auth cache)
- `documents/cdc/shares/user_shares_current.parquet` (Sharing cache)
- `documents/cdc/scheduled_financials/scheduled_financials_current.parquet` (Financial cache)
- `documents/receipts/*` (Uploaded receipts/documents)
- `documents/backup/*` (Table backups)

**Why direct access?**
- **Speed**: Sub-millisecond auth lookups without Iceberg overhead
- **Simplicity**: CDC caches don't need versioning/time-travel
- **Documents**: User uploads aren't structured table data

### CDC Caches vs Iceberg Tables

**CDC (Change Data Capture) Caches** are optimized read replicas:

| Feature | CDC Cache | Iceberg Table |
|---------|-----------|---------------|
| Location | `documents/cdc/*/` | `warehouse/*/` |
| Purpose | Fast lookups | Full data with history |
| Access | Direct ADLS | Via Lakekeeper |
| Updates | Immediate on write | Append-only snapshots |
| Versioning | Single version | Full time-travel |
| Use Case | Auth, sharing checks | Queries, analytics |

**Example: User Authentication**
```python
# Fast path: Check CDC cache (1ms)
cache_df = pd.read_parquet("documents/cdc/users/users_current.parquet")
user = cache_df[cache_df.email == email]

# Slow path: Query Iceberg table (50ms+)
table = catalog.load_table("investflow.users")
user = table.scan().filter(...).to_pandas()
```

### What Happens When Lakekeeper Catalog is Reset?

**❌ Lost:**
- PostgreSQL metadata (table schemas, locations)
- Ability to query Iceberg tables via PyIceberg
- Snapshot history visibility

**✅ Still Safe:**
- **All parquet data files in ADLS** (immutable!)
- CDC caches (directly accessed)
- Document uploads
- Backups

**Recovery Process:**
1. Restore PostgreSQL from backup (7-day retention)
2. Extract table metadata and file locations
3. Download data files from ADLS
4. Re-import to new Iceberg tables

See `DATA_RECOVERY_SUMMARY.md` for the actual recovery performed on 2025-12-07.

### Connection Flow Summary

```
Frontend (localhost:3000)
    ↓ HTTP/REST API + JWT
Backend (localhost:8000)
    ├─→ Direct ADLS Access
    │   ├─ Auth cache (fast)
    │   ├─ Sharing cache
    │   └─ Document uploads
    │
    └─→ PyIceberg Client
        ↓
    Lakekeeper (localhost:8181)
        ↓ Query metadata
    PostgreSQL (Azure)
        ↓ Returns: "Table at abfss://..."
    Backend reads directly from ADLS
        ↓
    ADLS (investflowadls)
        └─ Parquet data files
```

### Key Takeaways

1. **Lakekeeper is just a catalog** - it doesn't store your data, only pointers
2. **PostgreSQL is just metadata** - losing it doesn't lose data
3. **ADLS is the source of truth** - all data lives here permanently
4. **Iceberg files are immutable** - they're never modified or deleted
5. **CDC caches are optional** - they're just for performance
6. **Always backup before catalog operations** - run `uv run backup_iceberg_tables.py`

## Data Backup and Recovery

### Backup Location

All data backups are stored in Azure ADLS:
- **Container**: `documents`
- **Folder**: `backup/YYYYMMDD_HHMMSS/`
- **Latest backup**: `backup/20251207_155844/`

### Backup Contents

The backup folder contains 12 parquet files - one for each Iceberg table in the `investflow` namespace:

| File | Records | Description |
|------|---------|-------------|
| `users.parquet` | 5 | User account records |
| `user_shares.parquet` | 1 | Bidirectional property sharing records |
| `properties.parquet` | 7 | Property records |
| `property_plan.parquet` | 3 | Property plan/tax records |
| `units.parquet` | 2 | Multi-unit property records |
| `document_metadata.parquet` | 110 | Document metadata records |
| `expenses.parquet` | 99 | Expense records |
| `clients.parquet` | 3 | Client/tenant records |
| `rents.parquet` | 3 | Rent payment records |
| `scenarios.parquet` | 2 | Investment scenario records |
| `scheduled_expenses.parquet` | 34 | Scheduled/planned expenses |
| `scheduled_revenue.parquet` | 4 | Scheduled/planned revenue |

**Total**: 273 records across all tables

### How to Create a Backup

To backup all Iceberg tables to Azure ADLS:

```bash
cd backend
uv run backup_iceberg_tables.py
```

This will:
1. Connect to the Lakekeeper Iceberg catalog
2. Read all 12 tables from the `investflow` namespace
3. Automatically detect and remove duplicate records
4. Export each table to parquet format
5. Upload to Azure ADLS in `documents/backup/YYYYMMDD_HHMMSS/`
6. Provide a summary of records and file sizes

### How to Restore Data from Backup

If you need to restore data from the Azure ADLS backup:

#### Prerequisites
```bash
cd backend
# Ensure Azure credentials are configured in .env
# AZURE_STORAGE_ACCOUNT_NAME=investflowadls
# AZURE_STORAGE_ACCOUNT_KEY=<your-key>
```

#### Step 1: Download Backup Files
```bash
# Download specific backup folder
az storage blob download-batch \
  --account-name investflowadls \
  --source documents \
  --pattern "backup/20251207_151118/*.parquet" \
  --destination ./restore_data/ \
  --account-key $AZURE_STORAGE_ACCOUNT_KEY
```

#### Step 2: Validate Backup Files
```bash
# Run validation script
uv run validate_azure_backup.py
```

This will verify:
- All parquet files are readable
- Record counts match expected values
- Column schemas are valid
- Totals are correct (for expense/revenue files)

#### Step 3: Restore to Iceberg Tables

Create a restore script or use the existing pattern:

```python
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from app.core.config import settings

# Initialize catalog
catalog = RestCatalog(
    name="lakekeeper",
    uri=settings.LAKEKEEPER__BASE_URI + "/catalog",
    warehouse=settings.LAKEKEEPER__WAREHOUSE_NAME,
    **{
        "credential": f"{settings.LAKEKEEPER__OAUTH2__CLIENT_ID}:{settings.LAKEKEEPER__OAUTH2__CLIENT_SECRET}",
        "oauth2-server-uri": f"https://login.microsoftonline.com/{settings.LAKEKEEPER__OAUTH2__TENANT_ID}/oauth2/v2.0/token",
        "scope": settings.LAKEKEEPER__OAUTH2__SCOPE
    }
)

# Load data
df = pd.read_parquet('restore_data/expenses.parquet')

# Get table and append
table = catalog.load_table("investflow.expenses")
arrow_table = pa.Table.from_pandas(df, schema=table.schema().as_arrow())
table.append(arrow_table)
```

#### Step 4: Verify Restored Data
```bash
# Check record counts in Iceberg tables
uv run -m app.scripts.verify_data
```

### Important Notes

1. **Iceberg Data Persistence**: Iceberg data files in ADLS are immutable and never deleted automatically. Only the catalog metadata (PostgreSQL) can be lost.

2. **Point-in-Time Recovery**: Azure PostgreSQL has 7-day automatic backups for point-in-time restore of catalog metadata.

3. **Backup Frequency**: Create backups before:
   - Major schema changes
   - Catalog resets or migrations
   - Production deployments
   - Bulk data operations

4. **Schema Evolution**: When restoring, ensure the backup data schema matches the current Iceberg table schema. Missing columns will be added with null values.

### Recovery from Catalog Loss

If the Lakekeeper catalog (PostgreSQL) is lost or reset:

1. **Restore PostgreSQL Database** (if within 7-day backup window):
   ```bash
   az postgres flexible-server restore \
     --resource-group investflow-rg \
     --name if-postgres \
     --source-server if-postgres \
     --restore-time "2025-12-07T16:40:00Z" \
     --name if-postgres-restored
   ```

2. **Extract Table Locations**: Query restored database for Iceberg table metadata and data file locations

3. **Download Data Files**: Use metadata to download parquet files from ADLS

4. **Restore to Current Catalog**: Append recovered data to new Iceberg tables

See `DATA_RECOVERY_SUMMARY.md` for detailed recovery procedure used on 2025-12-07.

## EMERGENCY RECOVERY: If Lakekeeper Catalog Gets Deleted

**⚠️ CRITICAL: DO NOT RUN `reset_lakekeeper.py` **

If the Lakekeeper PostgreSQL metadata gets deleted (tables dropped, wrong encryption key, etc.):

### Your Data is SAFE
- ✅ All Iceberg data in Azure ADLS is intact (parquet files are immutable)
- ✅ CDC caches are intact (users, shares, scheduled financials)
- ✅ Document uploads are intact
- ❌ Only the catalog metadata (table locations, schemas) is lost

### Quick Recovery Steps

#### Step 1: Create the Warehouse

The warehouse creation requires specific credential format. Here's the EXACT command that works:

```bash
cd /Users/matt/code/property/backend

# Get OAuth2 token from Azure AD
TENANT_ID=$(grep LAKEKEEPER__OAUTH2__TENANT_ID .env | cut -d'=' -f2)
CLIENT_ID=$(grep LAKEKEEPER__OAUTH2__CLIENT_ID .env | cut -d'=' -f2)
CLIENT_SECRET=$(grep LAKEKEEPER__OAUTH2__CLIENT_SECRET .env | cut -d'=' -f2)
SCOPE=$(grep LAKEKEEPER__OAUTH2__SCOPE .env | cut -d'=' -f2)
STORAGE_KEY=$(grep AZURE_STORAGE_ACCOUNT_KEY .env | cut -d'=' -f2)

TOKEN=$(curl -s -X POST "https://login.microsoftonline.com/$TENANT_ID/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$CLIENT_ID&scope=$SCOPE&client_secret=$CLIENT_SECRET&grant_type=client_credentials" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Create warehouse with storage credential
curl -X POST http://localhost:8181/management/v1/warehouse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"warehouse-name\": \"lakekeeper\",
    \"project-id\": \"00000000-0000-0000-0000-000000000000\",
    \"storage-profile\": {
      \"type\": \"azdls\",
      \"account-name\": \"investflowadls\",
      \"filesystem\": \"documents\"
    },
    \"storage-credential\": {
      \"type\": \"az\",
      \"credential-type\": \"shared-access-key\",
      \"key\": \"$STORAGE_KEY\"
    }
  }" | python3 -m json.tool
```

**Expected Output:**
```json
{
    "warehouse-id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

#### Step 2: Restart Backend

```bash
cd /Users/matt/code/property/backend
docker compose restart backend
sleep 10
```

#### Step 3: Test Properties Endpoint

```bash
# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "matt.pappasemail@gmail.com", "password": "levi0210"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Test properties endpoint
curl -s http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Expected:** Should return your 7 properties (316 S 50th Ave, 1621 Washington, etc.)

### If Properties Don't Appear: Restore from PostgreSQL Backup

If the warehouse creation doesn't automatically discover your tables:

```bash
# Restore PostgreSQL to before the deletion
az postgres flexible-server restore \
  --resource-group investflow-rg \
  --name if-postgres-restored-$(date +%Y%m%d) \
  --source-server if-postgres \
  --restore-time "2025-12-21T22:13:00Z"  # CHANGE THIS TO 1 MINUTE BEFORE DELETION

# Wait 10-15 minutes for restore to complete
az postgres flexible-server show --resource-group investflow-rg --name if-postgres-restored-$(date +%Y%m%d) --query state

# Once "Ready", run the restore script:
cd /Users/matt/code/property/backend
bash restore_catalog.sh  # This script dumps from restored DB and imports to current DB

# Restart containers
docker compose restart lakekeeper backend
```

### Prevention Tips

1. **Never run `reset_lakekeeper.py` without PostgreSQL backups ready**
2. **Backup before any catalog operations:** `uv run backup_iceberg_tables.py`
3. **Azure PostgreSQL has 7-day automatic backups** - use them!
4. **Test locally first** - always verify changes work before deploying

### Common Mistakes That Lead Here

❌ Running `reset_lakekeeper.py` due to encryption key mismatch  
❌ Changing `LAKEKEEPER__PG_ENCRYPTION_KEY` without migrating secrets  
❌ Dropping PostgreSQL tables manually  
❌ Deleting the warehouse without backup  

### Key Insight

**Lakekeeper is just a catalog.** It points to data in Azure ADLS but doesn't store the data itself. Losing the catalog is recoverable because:
1. The Iceberg metadata files exist in Azure ADLS (`documents/` filesystem)
2. Azure PostgreSQL has 7-day point-in-time restore
3. Recreating the warehouse can sometimes auto-discover tables

**Last Recovery:** 2025-12-21 (warehouse recreation successful)
