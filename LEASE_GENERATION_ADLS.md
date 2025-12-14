# Lease Generation System - ADLS Storage Architecture

## Overview

The lease generation system stores **all files in Azure Data Lake Storage (ADLS)**, ensuring consistency between local development and production environments. Both environments share the same ADLS account, so changes made locally are immediately visible in production and vice versa.

## Storage Architecture

### ADLS Folder Structure

```
documents/  (ADLS container)
├── leases/
│   ├── generated/
│   │   └── {user_id}/
│   │       └── {lease_id}/
│   │           ├── lease_316_S_50th_Ave_20251214_084830.pdf
│   │           └── lease_316_S_50th_Ave_20251214_084830.tex
│   └── temp/
│       └── {temporary compilation files - auto-cleaned}
├── expenses/
│   └── {user_id}/
│       └── {receipt files}
└── user_documents/
    └── {user_id}/
        └── {other document files}
```

### Why ADLS for Everything?

1. **Shared State**: Local and production environments use the same ADLS account
2. **Data Consistency**: Files created locally are immediately available in production
3. **No Sync Issues**: No need to sync files between environments
4. **Backup & Recovery**: All files automatically backed up by Azure
5. **Audit Trail**: ADLS blob metadata tracks who created what and when

## Lease Generation Flow

### 1. User Creates Lease (Frontend → Backend)

```
User fills lease form → POST /api/v1/leases
                      ↓
Backend validates data → Applies state-specific defaults
                      ↓
Saves to Iceberg table → investflow.leases
                      ↓
Saves tenants → investflow.lease_tenants
```

### 2. PDF Generation

```
Backend retrieves lease data → Builds LaTeX document
                            ↓
Saves LaTeX to ADLS → leases/generated/{user_id}/{lease_id}/lease.tex
                            ↓
Compiles with pdflatex → (uses local /tmp/ for compilation only)
                            ↓
Saves PDF to ADLS → leases/generated/{user_id}/{lease_id}/lease.pdf
                            ↓
Updates lease record → generated_pdf_document_id
```

### 3. Document Retrieval

```
User requests PDF → GET /api/v1/leases/{id}/pdf
                 ↓
Backend retrieves blob_name from lease record
                 ↓
Generates SAS URL from ADLS → 24-hour expiring download link
                 ↓
Returns signed URL to frontend
```

## Temporary File Usage

### Compilation Directory (`/tmp/` on local filesystem)

**Only used during PDF compilation** - files are immediately deleted after compilation:

```python
with tempfile.TemporaryDirectory() as tmpdir:
    # Write .tex file
    # Run pdflatex twice
    # Read .pdf file
    # Directory auto-deleted
    # PDF bytes uploaded to ADLS
```

**Why local `/tmp/` for compilation?**
- pdflatex requires local filesystem access
- Creates multiple intermediate files (.aux, .log, etc.)
- Faster than writing/reading from ADLS for each intermediate file
- Temp directory is automatically cleaned up after compilation

**Important**: The final PDF and LaTeX source are **always** saved to ADLS, never left in `/tmp/`.

## Database Records

### `investflow.leases` Table

Key fields for document storage:

```python
{
    "id": "uuid",
    "user_id": "uuid",  # Landlord
    "property_id": "uuid",
    "generated_pdf_document_id": "blob_name_in_adls",  # NEW
    "template_used": "NE_residential_v1",
    # ... all lease terms ...
}
```

### `investflow.lease_tenants` Table

```python
{
    "id": "uuid",
    "lease_id": "uuid",
    "tenant_order": 1,
    "first_name": "John",
    "last_name": "Doe",
    # ... tenant info ...
}
```

## Code Structure

### Services

1. **`lease_defaults.py`**
   - Centralized default values
   - State-specific rules (NE vs MO)
   - Default move-out costs

2. **`lease_generator_service.py`**
   - Builds LaTeX from lease data
   - Compiles PDF using pdflatex
   - **Saves all files to ADLS**
   - Returns blob names for database storage

3. **`adls_service.py`** (existing)
   - Upload/download blobs
   - Generate SAS URLs
   - Manage blob metadata

### Scripts

1. **`upload_316_lease.py`**
   - Creates sample lease for 316 S 50th Ave
   - Uploads to Iceberg tables
   - Generates PDF and saves to ADLS
   - Validates entire pipeline

2. **`compare_lease_output.py`**
   - Downloads PDF from ADLS
   - Compares to template
   - Validates section structure and terms

## Environment Configuration

### Required Environment Variables

```bash
# Azure Storage (ADLS)
AZURE_STORAGE_ACCOUNT_NAME=investflowadls
AZURE_STORAGE_ACCOUNT_KEY=<key>
AZURE_STORAGE_CONTAINER_NAME=documents

# Or use connection string
AZURE_STORAGE_CONNECTION_STRING=<connection_string>
```

### Docker Container (TinyTeX)

The backend Dockerfile includes TinyTeX for PDF generation:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ wget perl curl \
    && wget -qO- "https://yihui.org/tinytex/install-bin-unix.sh" | sh \
    && /root/bin/tlmgr install enumitem titlesec fancyhdr tabularx \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/bin:$PATH"
```

## Testing

### Local Development (without pdflatex)

```bash
cd backend
uv run app/scripts/upload_316_lease.py
```

**Result**:
- ✓ Lease data saved to Iceberg
- ✓ Tenant data saved to Iceberg
- ⚠ PDF generation skipped (pdflatex not found)
- → All data ready for production PDF generation

### Docker Environment (with TinyTeX)

```bash
cd backend
docker-compose up --build
docker exec -it backend-container uv run app/scripts/upload_316_lease.py
```

**Result**:
- ✓ Lease data saved to Iceberg
- ✓ Tenant data saved to Iceberg
- ✓ PDF generated and saved to ADLS
- ✓ LaTeX source saved to ADLS

## State-Specific Rules

### Nebraska (NE)

- Security deposit: Up to 1 month's rent
- Deposit return: 14 days
- Late fees: Progressive ($75 → $150 → $225)
- No methamphetamine disclosure required

### Missouri (MO)

- Security deposit: Up to 2 months' rent
- Deposit return: 30 days
- Late fees: Must be "reasonable" (conservative approach)
- Methamphetamine disclosure: **Required**
- Move-out inspection rights: **Required**
- Military termination: 30 days notice

## ADLS Benefits

### 1. No Sync Issues
Both local and production read from the same ADLS account, eliminating sync problems.

### 2. Immediate Availability
Files created locally are immediately available in production without deployment.

### 3. Audit Trail
Every blob has metadata:
```python
{
    "user_id": "uuid",
    "lease_id": "uuid",
    "property_id": "uuid",
    "generated_at": "2025-12-14T08:48:30Z",
    "document_type": "lease_pdf"
}
```

### 4. Access Control
SAS URLs provide time-limited, secure access without exposing storage keys.

### 5. Backup & Recovery
Azure automatically backs up ADLS data with geo-redundancy.

## Future Enhancements

1. **Signature Capture**: Store signed PDFs in ADLS
2. **Version History**: Keep all lease versions in ADLS
3. **Template Library**: Store LaTeX templates in ADLS
4. **Bulk Generation**: Generate leases for multiple properties
5. **Email Integration**: Email PDF directly from ADLS SAS URL

## Summary

✅ **All permanent storage in ADLS**  
✅ **Local `/tmp/` only for compilation (auto-cleaned)**  
✅ **Both environments share same ADLS**  
✅ **No manual file syncing required**  
✅ **Production-ready architecture**

---

**Last Updated**: December 14, 2025  
**System**: InvestFlow Lease Generation v1.0

