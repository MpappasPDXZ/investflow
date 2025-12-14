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

## Deployment

### Quick Deploy (Update Existing Containers)

If you've already pushed images to Azure Container Registry and just need to update the running containers without rebuilding:

```bash
# Update frontend only
az containerapp update --name investflow-frontend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-frontend:latest

# Update backend only
az containerapp update --name investflow-backend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-backend:latest

# Update both
az containerapp update --name investflow-frontend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-frontend:latest && \
az containerapp update --name investflow-backend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-backend:latest
```

**Note**: This assumes you've already built and pushed the latest images to Azure Container Registry. To build and push:

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

### Full Deployment

For a complete deployment including building images, use `./deploy.sh` (requires ~5-10GB free disk space)

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
