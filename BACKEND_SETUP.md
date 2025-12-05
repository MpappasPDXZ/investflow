# Backend Setup Guide - Expense & Document Management

## Prerequisites

- Python 3.10+
- Azure Storage Account configured
- Lakekeeper/Iceberg catalog running
- PostgreSQL database (optional, for hybrid approach)

## Installation

### 1. Install Python Dependencies

```bash
cd backend
pip install azure-storage-blob azure-identity pyarrow
```

Or add to `pyproject.toml`:
```toml
[project]
dependencies = [
    "azure-storage-blob>=12.19.0",
    "azure-identity>=1.15.0",
    "pyarrow>=14.0.0",
    # ... existing dependencies
]
```

### 2. Configure Environment Variables

Update your `.env` file:

```bash
# Azure Storage (already configured)
AZURE_STORAGE_ACCOUNT_NAME=investflowadls
AZURE_STORAGE_ACCOUNT_KEY=<your_key>
AZURE_STORAGE_CONTAINER_NAME=documents

# Lakekeeper (already configured)
LAKEKEEPER__BASE_URI=http://localhost:8181
LAKEKEEPER__WAREHOUSE_NAME=lakekeeper
```

### 3. Create Iceberg Tables

```bash
# Create document metadata table
python create_document_metadata_table.py

# Create expenses table
python create_expenses_table.py
```

### 4. Run Database Migration (if using PostgreSQL)

```bash
# Add unit_id to expenses table
psql -h <host> -U <user> -d <database> -f add_unit_id_to_expenses.sql
```

## API Endpoints

### Documents API (`/api/v1/documents`)

#### Upload Document
```
POST /documents/upload
Content-Type: multipart/form-data

Fields:
- file: File (required)
- document_type: string (receipt|lease|screening|invoice|other)
- property_id: UUID (optional)
- unit_id: UUID (optional)

Response: {document: {...}, download_url: "..."}
```

#### List Documents
```
GET /documents?property_id={uuid}&unit_id={uuid}&document_type={type}&skip=0&limit=100

Response: {items: [...], total: 10, page: 1, limit: 100}
```

#### Get Document
```
GET /documents/{document_id}

Response: {id: "...", file_name: "...", ...}
```

#### Get Download URL
```
GET /documents/{document_id}/download

Response: {download_url: "https://..."}
```

#### Delete Document
```
DELETE /documents/{document_id}

Response: 204 No Content
```

### Expenses API (`/api/v1/expenses`)

#### Create Expense
```
POST /expenses
Content-Type: application/json

Body: {
  property_id: "uuid",
  unit_id: "uuid" (optional),
  description: "string",
  date: "2025-01-15",
  amount: 123.45,
  vendor: "string" (optional),
  expense_type: "capex|pandi|utilities|maintenance|insurance|property_management|other",
  document_storage_id: "uuid" (optional),
  is_planned: false,
  notes: "string" (optional)
}
```

#### Create Expense with Receipt
```
POST /expenses/with-receipt
Content-Type: multipart/form-data

Fields:
- file: File (required)
- property_id: UUID
- unit_id: UUID (optional)
- description: string
- date: ISO date string
- amount: decimal string
- vendor: string (optional)
- expense_type: string
- is_planned: boolean
- notes: string (optional)
- document_type: "receipt" (optional)
```

#### List Expenses
```
GET /expenses?property_id={uuid}&unit_id={uuid}&start_date={date}&end_date={date}&expense_type={type}&skip=0&limit=100

Response: {items: [...], total: 10, page: 1, limit: 100}
```

#### Get Expense Summary (with Yearly Subtotals)
```
GET /expenses/summary?property_id={uuid}&year={2025}

Response: {
  yearly_totals: [
    {year: 2025, total: 12345.67, count: 15, by_type: {capex: 5000, ...}},
    {year: 2024, total: 10000.00, count: 12, by_type: {capex: 4000, ...}}
  ],
  type_totals: {capex: 9000, pandi: 8000, ...},
  grand_total: 22345.67,
  total_count: 27
}
```

#### Get Expense
```
GET /expenses/{expense_id}
```

#### Update Expense
```
PUT /expenses/{expense_id}
Content-Type: application/json

Body: {... partial fields to update ...}
```

#### Delete Expense
```
DELETE /expenses/{expense_id}

Response: 204 No Content
```

#### Get Expense Receipt
```
GET /expenses/{expense_id}/receipt

Response: {download_url: "https://..."}
```

## Architecture

### Data Flow

1. **Document Upload**:
   - Frontend uploads file to backend API
   - Backend uploads to ADLS (Azure Blob Storage)
   - Backend writes metadata to Iceberg table
   - Backend returns document ID and SAS URL

2. **Expense Creation with Receipt**:
   - Frontend uploads file + expense data
   - Backend uploads document first
   - Backend creates expense with document_storage_id link
   - Returns expense with embedded document info

3. **Document Retrieval**:
   - Frontend requests document/expense
   - Backend queries Iceberg for metadata
   - Backend generates 24-hour SAS URL
   - Frontend displays PDF/image

### Storage Layers

- **ADLS (Azure Data Lake Storage)**: Raw files (PDFs, images)
- **Iceberg Tables**: Metadata pointers, queryable, versioned
- **PostgreSQL** (optional): Transactional data, foreign keys

### File Organization in ADLS

```
documents/
  {user_id}/
    receipt/
      {uuid}.pdf
      {uuid}.jpg
    lease/
      {uuid}.pdf
    screening/
      {uuid}.pdf
    other/
      {uuid}.pdf
```

## Testing

### Test Document Upload

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer {token}" \
  -F "file=@receipt.pdf" \
  -F "document_type=receipt" \
  -F "property_id={uuid}"
```

### Test Expense with Receipt

```bash
curl -X POST http://localhost:8000/api/v1/expenses/with-receipt \
  -H "Authorization: Bearer {token}" \
  -F "file=@receipt.pdf" \
  -F "property_id={uuid}" \
  -F "description=Floor scraper" \
  -F "date=2025-09-12" \
  -F "amount=82.79" \
  -F "vendor=Home Depot" \
  -F "expense_type=capex"
```

### Test Expense Summary

```bash
curl -X GET "http://localhost:8000/api/v1/expenses/summary?property_id={uuid}" \
  -H "Authorization: Bearer {token}"
```

## Troubleshooting

### Azure Storage Issues

1. Check environment variables are set
2. Verify storage account key is correct
3. Ensure container exists (auto-created if not)

### Iceberg Issues

1. Verify Lakekeeper is running: `curl http://localhost:8181/health`
2. Check catalog configuration in `warehouse.json`
3. Run table creation scripts

### Import Issues

If you see import errors:
```bash
pip install --upgrade azure-storage-blob pyarrow
```

## Performance Considerations

- SAS URLs expire after 24 hours for security
- Iceberg partitions by year for efficient queries
- Documents cached in Iceberg metadata for fast lookups
- Soft deletes keep audit trail

## Security

- All file uploads validated (type, size)
- SAS URLs time-limited and read-only
- User access controlled via Iceberg filters
- Document metadata isolated by user_id






