# Expense & Document Management Implementation Plan

## Overview
This document outlines the complete implementation of a CPA-ready expense management system with document storage in Azure Data Lake Storage (ADLS) and Iceberg metadata tables.

## Backend Architecture

### 1. Data Storage
- **Azure Data Lake Storage (ADLS)**: Stores actual document files (PDFs, images)
- **Iceberg Tables**: Stores metadata pointers to documents
- **PostgreSQL/Iceberg**: Stores expense transaction data

### 2. Iceberg Tables

#### document_metadata table
```
- id (string): Document UUID
- user_id (string): User who uploaded
- property_id (string, optional): Associated property
- unit_id (string, optional): Associated unit  
- blob_location (string): Full ADLS path
- container_name (string): Azure container
- blob_name (string): Blob path
- file_name (string): Original filename
- file_type (string): MIME type
- file_size (long): Size in bytes
- document_type (string): receipt|lease|screening|invoice|other
- document_metadata (map<string,string>): Additional metadata
- uploaded_at (timestamp): Upload time
- expires_at (timestamp, optional): Expiration
- is_deleted (boolean): Soft delete flag
- created_at, updated_at (timestamps)

Partitioned by: upload_year
```

#### expenses table (existing, enhanced)
```
Already has:
- id, property_id, description, date, amount
- vendor, expense_type, document_storage_id
- is_planned, notes, created_by_user_id

Will add:
- unit_id (optional): Link to specific unit
```

### 3. Backend Services

#### ADLS Service (`app/services/adls_service.py`)
- Upload blobs to ADLS
- Generate SAS URLs for downloads (24-hour expiry)
- Delete blobs
- Check blob existence

#### Document Service (`app/services/document_service.py`)
- Upload documents (ADLS + Iceberg metadata)
- Retrieve document metadata
- Generate download URLs
- List documents with filters
- Soft delete documents

#### Expense Service (TO CREATE: `app/services/expense_service.py`)
- Create/update/delete expenses
- Link expenses to documents
- Query expenses by property/unit/date/type
- Generate expense reports with yearly subtotals

### 4. API Endpoints

#### Documents API (`/api/v1/documents`)
- POST `/upload` - Upload document
- GET `/{document_id}` - Get document metadata
- GET `/{document_id}/download` - Get download URL
- GET `` - List documents (filterable by property/unit/type)
- DELETE `/{document_id}` - Soft delete document

#### Expenses API (`/api/v1/expenses`)
- POST `` - Create expense
- POST `/with-receipt` - Create expense with receipt upload
- GET `` - List expenses (filterable by property/unit/date/type)
- GET `/{expense_id}` - Get expense details
- GET `/{expense_id}/receipt` - Get receipt download URL
- PUT `/{expense_id}` - Update expense
- DELETE `/{expense_id}` - Delete expense
- GET `/summary` - Get expense summary with yearly subtotals

## Frontend Implementation

### 1. Components

#### ReceiptViewer Component
- Display PDF receipts (using react-pdf or iframe)
- Display image receipts (JPEG, PNG)
- Download button
- Zoom/pan controls for images
- Print functionality

#### DocumentUploadComponent
- Drag-and-drop file upload
- File type validation (PDF, JPEG, PNG)
- Size validation (max 10MB)
- Progress indicator
- Preview uploaded document

#### ExpenseTable Component
- Sortable columns: Date, Amount, Item, Type, Receipt
- Filter by property, unit, date range, expense type
- **Yearly subtotals** (group by year, sum amounts)
- Receipt icon/link for expenses with documents
- Click to view receipt inline
- Edit/delete actions
- Export to CSV/Excel for CPA

#### DocumentManagementScreen
- Tabs for different document types:
  - All Documents
  - Receipts
  - Leases
  - Screenings
  - Other
- Grid/list view toggle
- Thumbnail previews
- Upload button
- Filter by property/unit
- Bulk operations (delete, download)

### 2. Pages

#### /expenses Page
- Property/Unit selector
- Date range picker
- Expense type filter
- ExpenseTable with yearly subtotals
- "Add Expense" button
- Export button

#### /expenses/add Page
- Form fields:
  - Property (required)
  - Unit (optional, if multi-unit)
  - Date
  - Amount
  - Description/Item
  - Vendor
  - Expense Type (dropdown from scheduled types)
  - Notes
- Document upload component
- Save button

#### /documents/lease, /documents/screenings, /documents/other Pages
- Document upload form
- Property/Unit selector
- DocumentManagementScreen component
- Filter and search

### 3. API Client Functions

```typescript
// Document functions
uploadDocument(file, documentType, propertyId?, unitId?)
getDocument(documentId)
getDocumentDownloadUrl(documentId)
listDocuments(propertyId?, unitId?, documentType?)
deleteDocument(documentId)

// Expense functions
createExpense(expenseData)
createExpenseWithReceipt(expenseData, file)
getExpense(expenseId)
listExpenses(propertyId?, unitId?, startDate?, endDate?, expenseType?)
getExpenseSummary(propertyId?, year?)
updateExpense(expenseId, expenseData)
deleteExpense(expenseId)
getExpenseReceipt(expenseId)
```

## Database Schema Updates

### Add unit_id to expenses table
```sql
ALTER TABLE expenses 
ADD COLUMN unit_id UUID REFERENCES units(id) ON DELETE CASCADE;

CREATE INDEX idx_expenses_unit ON expenses(unit_id);
```

## Configuration

### Environment Variables
```
# Azure Storage (already configured)
AZURE_STORAGE_ACCOUNT_NAME=investflowadls
AZURE_STORAGE_ACCOUNT_KEY=<key>
AZURE_STORAGE_CONTAINER_NAME=documents

# Lakekeeper/Iceberg (already configured)
LAKEKEEPER__BASE_URI=http://localhost:8181
LAKEKEEPER__WAREHOUSE_NAME=lakekeeper
```

## Setup Instructions

### 1. Create Iceberg Table
```bash
cd backend
python create_document_metadata_table.py
```

### 2. Install Python Dependencies
```bash
cd backend
pip install azure-storage-blob azure-identity pyarrow
```

### 3. Install Frontend Dependencies
```bash
cd frontend
npm install react-pdf @react-pdf-viewer/core @react-pdf-viewer/default-layout
```

### 4. Run Database Migration
```sql
-- Add unit_id to expenses
ALTER TABLE expenses ADD COLUMN unit_id UUID REFERENCES units(id) ON DELETE CASCADE;
CREATE INDEX idx_expenses_unit ON expenses(unit_id);
```

## Features Summary

✅ **Document Storage**
- Store receipts, leases, screenings in ADLS
- Metadata in Iceberg for fast querying
- SAS URLs for secure downloads (24-hour expiry)
- Soft deletes (metadata marked deleted, files retained)

✅ **Expense Tracking**
- Link expenses to properties and units
- Attach receipts to expenses
- Filter by date, property, unit, type
- **Yearly subtotals for CPA reporting**

✅ **Document Management**
- Upload documents for properties/units
- View documents by type
- Download/preview documents
- Organize leases, screenings, other docs

✅ **CPA-Ready**
- Structured expense data with receipts
- Yearly subtotals for tax reporting
- Export capabilities
- Audit trail (created_at, updated_at)

## Next Steps

1. ✅ Create document_metadata Iceberg table
2. ✅ Implement ADLS service
3. ✅ Implement document service
4. 🔄 Implement expense service
5. 🔄 Update expense API routes
6. 🔄 Update document API routes
7. 🔄 Build frontend components
8. 🔄 Build expense page with yearly subtotals
9. 🔄 Build document management pages
10. 🔄 Test end-to-end workflow

## File Naming Convention

For uploaded files in ADLS:
```
{user_id}/{document_type}/{uuid}.{ext}

Examples:
user123/receipt/abc-def-123.pdf
user123/lease/xyz-789-456.pdf
user456/screening/screening-001.pdf
```

This organization allows for:
- Easy user-based access control
- Document type grouping
- Unique filenames to prevent conflicts
- Simple cleanup of user data if needed

