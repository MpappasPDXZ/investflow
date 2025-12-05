# Frontend Development Context - Expense & Document Management

## Project Status

### ✅ COMPLETED - Backend Infrastructure

All backend services are fully implemented and ready to use:

1. **Iceberg Tables Created**
   - `document_metadata` - Stores document pointers to ADLS
   - `expenses` - Stores expense records with document links

2. **Services Implemented**
   - `app/services/adls_service.py` - Azure blob storage operations
   - `app/services/document_service.py` - Document management with Iceberg
   - `app/services/expense_service.py` - Expense CRUD with yearly summaries

3. **API Endpoints Ready**
   - `/api/v1/documents/*` - Full CRUD for documents
   - `/api/v1/expenses/*` - Full CRUD for expenses with summary endpoint

### 🔄 TODO - Frontend Components (CURRENT FOCUS)

Need to build 4 main components:

1. **Document Upload Component** - Drag-drop file upload with preview
2. **Receipt Viewer Component** - Display PDF/images inline
3. **Expense Table with Yearly Subtotals** - CPA-ready expense list
4. **Document Management Screen** - Browse/manage all documents

---

## API Reference for Frontend

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication
All requests require Bearer token:
```typescript
headers: {
  'Authorization': `Bearer ${token}`
}
```

### Documents API

#### 1. Upload Document
```typescript
POST /documents/upload
Content-Type: multipart/form-data

// FormData fields:
const formData = new FormData();
formData.append('file', file); // File object
formData.append('document_type', 'receipt'); // receipt|lease|screening|invoice|other
formData.append('property_id', propertyId); // optional UUID
formData.append('unit_id', unitId); // optional UUID

// Response:
{
  document: {
    id: "uuid",
    blob_location: "https://...",
    blob_name: "user123/receipt/uuid.pdf",
    file_name: "receipt.pdf",
    file_type: "application/pdf",
    file_size: 123456,
    document_type: "receipt",
    property_id: "uuid",
    unit_id: "uuid",
    uploaded_at: "2025-01-15T10:30:00Z",
    created_at: "2025-01-15T10:30:00Z",
    updated_at: "2025-01-15T10:30:00Z"
  },
  download_url: "https://investflowadls.blob.core.windows.net/documents/...?sas_token"
}
```

#### 2. List Documents
```typescript
GET /documents?property_id={uuid}&unit_id={uuid}&document_type={type}&skip=0&limit=100

// Response:
{
  items: [
    {
      id: "uuid",
      file_name: "receipt.pdf",
      file_type: "application/pdf",
      file_size: 123456,
      document_type: "receipt",
      property_id: "uuid",
      unit_id: "uuid",
      uploaded_at: "2025-01-15T10:30:00Z"
    }
  ],
  total: 10,
  page: 1,
  limit: 100
}
```

#### 3. Get Document Download URL
```typescript
GET /documents/{document_id}/download

// Response:
{
  download_url: "https://...?sas_token" // Valid for 24 hours
}
```

#### 4. Delete Document
```typescript
DELETE /documents/{document_id}
// Response: 204 No Content
```

### Expenses API

#### 1. Create Expense
```typescript
POST /expenses
Content-Type: application/json

// Body:
{
  property_id: "uuid",
  unit_id: "uuid", // optional
  description: "Floor scraper",
  date: "2025-09-12",
  amount: 82.79,
  vendor: "Home Depot",
  expense_type: "capex", // capex|pandi|utilities|maintenance|insurance|property_management|other
  document_storage_id: "uuid", // optional - link to receipt
  is_planned: false,
  notes: "Purchased for renovation"
}

// Response: ExpenseResponse (same structure as body + id, created_at, updated_at)
```

#### 2. Create Expense with Receipt (Single Request)
```typescript
POST /expenses/with-receipt
Content-Type: multipart/form-data

// FormData fields:
formData.append('file', file);
formData.append('property_id', propertyId);
formData.append('unit_id', unitId); // optional
formData.append('description', 'Floor scraper');
formData.append('date', '2025-09-12');
formData.append('amount', '82.79');
formData.append('vendor', 'Home Depot');
formData.append('expense_type', 'capex');
formData.append('is_planned', 'false');
formData.append('notes', 'Purchased for renovation');
formData.append('document_type', 'receipt');

// Response: ExpenseResponse with embedded document_storage_id
```

#### 3. List Expenses
```typescript
GET /expenses?property_id={uuid}&unit_id={uuid}&start_date={date}&end_date={date}&expense_type={type}&skip=0&limit=100

// Response:
{
  items: [
    {
      id: "uuid",
      property_id: "uuid",
      unit_id: "uuid",
      description: "Floor scraper",
      date: "2025-09-12",
      amount: 82.79,
      vendor: "Home Depot",
      expense_type: "capex",
      document_storage_id: "uuid", // null if no receipt
      is_planned: false,
      notes: "...",
      created_at: "...",
      updated_at: "..."
    }
  ],
  total: 25,
  page: 1,
  limit: 100
}
```

#### 4. Get Expense Summary (⭐ KEY FOR CPA REPORTING)
```typescript
GET /expenses/summary?property_id={uuid}&year={2025}

// Response:
{
  yearly_totals: [
    {
      year: 2025,
      total: 12345.67,
      count: 15,
      by_type: {
        capex: 5000.00,
        pandi: 3000.00,
        utilities: 1500.00,
        maintenance: 2845.67
      }
    },
    {
      year: 2024,
      total: 10000.00,
      count: 12,
      by_type: {
        capex: 4000.00,
        maintenance: 6000.00
      }
    }
  ],
  type_totals: {
    capex: 9000.00,
    pandi: 3000.00,
    utilities: 1500.00,
    maintenance: 8845.67
  },
  grand_total: 22345.67,
  total_count: 27
}
```

#### 5. Get Expense Receipt
```typescript
GET /expenses/{expense_id}/receipt

// Response:
{
  download_url: "https://...?sas_token"
}
```

---

## Frontend Component Specifications

### 1. Document Upload Component

**File:** `frontend/components/DocumentUpload.tsx`

**Requirements:**
- Drag-and-drop file upload area
- Click to browse files
- File type validation (PDF, JPEG, PNG only)
- Size validation (max 10MB)
- Upload progress indicator
- Preview uploaded document
- Property/Unit selector
- Document type dropdown (receipt, lease, screening, other)

**Example Structure:**
```tsx
interface DocumentUploadProps {
  propertyId?: string;
  unitId?: string;
  documentType?: 'receipt' | 'lease' | 'screening' | 'other';
  onUploadSuccess?: (document: DocumentResponse) => void;
}

export function DocumentUpload({ propertyId, unitId, documentType, onUploadSuccess }: DocumentUploadProps) {
  // Implementation with react-dropzone or similar
}
```

**Key Features:**
- Use FormData for multipart upload
- Show file preview before upload
- Display upload progress
- Handle errors gracefully
- Clear form after successful upload

### 2. Receipt Viewer Component

**File:** `frontend/components/ReceiptViewer.tsx`

**Requirements:**
- Display PDF files (using react-pdf or iframe)
- Display image files (JPEG, PNG)
- Zoom/pan controls for images
- Download button
- Print functionality
- Full-screen mode
- Loading state
- Error handling for missing/expired URLs

**Example Structure:**
```tsx
interface ReceiptViewerProps {
  documentId?: string;
  downloadUrl?: string;
  fileName: string;
  fileType: string;
}

export function ReceiptViewer({ documentId, downloadUrl, fileName, fileType }: ReceiptViewerProps) {
  // For PDF: use react-pdf or <iframe>
  // For images: use <img> with zoom controls
}
```

**Dependencies to Install:**
```bash
npm install react-pdf @react-pdf-viewer/core @react-pdf-viewer/default-layout
```

### 3. Expense Table with Yearly Subtotals

**File:** `frontend/app/(dashboard)/expenses/page.tsx`

**Requirements:**
- Sortable table columns: Date, Amount, Description, Type, Vendor, Receipt
- Filter by property, unit, date range, expense type
- **Group by year with subtotals** (like the image provided)
- Year sections collapsible/expandable
- Receipt icon/link for expenses with documents
- Click receipt to open ReceiptViewer in modal/dialog
- Edit/delete actions per row
- Export to CSV button
- Running totals per year
- Grand total at bottom

**Table Structure:**
```tsx
// Yearly grouping
2025 Expenses (Total: $12,345.67) [Expand/Collapse]
  Date       | Amount    | Description    | Type        | Vendor      | Receipt
  ---------------------------------------------------------------------------
  12/15/2025 | $1,234.56 | Floor tiles    | capex       | Home Depot  | 📄 View
  12/10/2025 | $89.50    | Plumbing fix   | maintenance | Joe's       | 📄 View
  ...
  Subtotal:  | $12,345.67

2024 Expenses (Total: $10,000.00) [Expand/Collapse]
  ...

GRAND TOTAL: $22,345.67
```

**Key Features:**
- Fetch expenses using `/expenses` endpoint
- Fetch summary using `/expenses/summary` endpoint
- Group expenses by year client-side
- Show receipt icon only if document_storage_id exists
- Click icon to fetch `/expenses/{id}/receipt` and show in modal
- Use existing UI components (Card, Table from shadcn/ui)

### 4. Document Management Screen

**File:** `frontend/app/(dashboard)/documents/page.tsx`

**Requirements:**
- Tabs for document types (All, Receipts, Leases, Screenings, Other)
- Grid view with thumbnails (PDF icon for PDFs, image preview for images)
- List view option
- Property/Unit filter dropdowns
- Search by filename
- Upload button (opens DocumentUpload modal)
- Bulk actions (delete selected)
- Click document to open ReceiptViewer
- Download button per document
- Sort by date, name, size

**Layout:**
```tsx
<Card>
  <CardHeader>
    <Tabs>
      <TabsList>
        <TabsTrigger value="all">All Documents</TabsTrigger>
        <TabsTrigger value="receipts">Receipts</TabsTrigger>
        <TabsTrigger value="leases">Leases</TabsTrigger>
        <TabsTrigger value="screenings">Screenings</TabsTrigger>
        <TabsTrigger value="other">Other</TabsTrigger>
      </TabsList>
    </Tabs>
    <div className="flex gap-2">
      <Select property_id /> 
      <Select unit_id />
      <Button onClick={openUploadModal}>Upload</Button>
    </div>
  </CardHeader>
  <CardContent>
    <DocumentGrid documents={documents} onDocumentClick={openViewer} />
  </CardContent>
</Card>
```

---

## API Client Functions to Add

**File:** `frontend/lib/api-client.ts`

Add these functions to the existing apiClient:

```typescript
// Document functions
export const documentApi = {
  upload: async (file: File, documentType: string, propertyId?: string, unitId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    if (propertyId) formData.append('property_id', propertyId);
    if (unitId) formData.append('unit_id', unitId);
    
    return apiClient.upload('/documents/upload', formData);
  },
  
  list: async (filters: {
    property_id?: string;
    unit_id?: string;
    document_type?: string;
    skip?: number;
    limit?: number;
  }) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined) params.append(key, String(value));
    });
    return apiClient.get(`/documents?${params.toString()}`);
  },
  
  getDownloadUrl: async (documentId: string) => {
    return apiClient.get(`/documents/${documentId}/download`);
  },
  
  delete: async (documentId: string) => {
    return apiClient.delete(`/documents/${documentId}`);
  }
};

// Expense functions
export const expenseApi = {
  create: async (expenseData: ExpenseCreate) => {
    return apiClient.post('/expenses', expenseData);
  },
  
  createWithReceipt: async (expenseData: any, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    Object.entries(expenseData).forEach(([key, value]) => {
      if (value !== undefined) formData.append(key, String(value));
    });
    return apiClient.upload('/expenses/with-receipt', formData);
  },
  
  list: async (filters: {
    property_id?: string;
    unit_id?: string;
    start_date?: string;
    end_date?: string;
    expense_type?: string;
    skip?: number;
    limit?: number;
  }) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined) params.append(key, String(value));
    });
    return apiClient.get(`/expenses?${params.toString()}`);
  },
  
  getSummary: async (propertyId?: string, year?: number) => {
    const params = new URLSearchParams();
    if (propertyId) params.append('property_id', propertyId);
    if (year) params.append('year', String(year));
    return apiClient.get(`/expenses/summary?${params.toString()}`);
  },
  
  getReceipt: async (expenseId: string) => {
    return apiClient.get(`/expenses/${expenseId}/receipt`);
  },
  
  update: async (expenseId: string, data: ExpenseUpdate) => {
    return apiClient.put(`/expenses/${expenseId}`, data);
  },
  
  delete: async (expenseId: string) => {
    return apiClient.delete(`/expenses/${expenseId}`);
  }
};
```

---

## TypeScript Types to Add

**File:** `frontend/lib/types.ts`

```typescript
export interface Document {
  id: string;
  blob_location: string;
  blob_name: string;
  file_name: string;
  file_type: string;
  file_size: number;
  document_type: 'receipt' | 'lease' | 'screening' | 'invoice' | 'other';
  property_id?: string;
  unit_id?: string;
  uploaded_at: string;
  created_at: string;
  updated_at: string;
}

export interface Expense {
  id: string;
  property_id: string;
  unit_id?: string;
  description: string;
  date: string;
  amount: number;
  vendor?: string;
  expense_type: 'capex' | 'pandi' | 'utilities' | 'maintenance' | 'insurance' | 'property_management' | 'other';
  document_storage_id?: string;
  is_planned: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ExpenseSummary {
  yearly_totals: Array<{
    year: number;
    total: number;
    count: number;
    by_type: Record<string, number>;
  }>;
  type_totals: Record<string, number>;
  grand_total: number;
  total_count: number;
}
```

---

## Implementation Order

1. **First:** Add API client functions and types
2. **Second:** Build ReceiptViewer component (simplest, reusable)
3. **Third:** Build DocumentUpload component (used by others)
4. **Fourth:** Build Expense table with yearly subtotals
5. **Fifth:** Build Document management screen

---

## Testing Checklist

- [ ] Upload PDF receipt
- [ ] Upload JPEG/PNG receipt  
- [ ] View PDF in ReceiptViewer
- [ ] View image in ReceiptViewer
- [ ] Create expense with receipt (single request)
- [ ] View expense table grouped by year
- [ ] See yearly subtotals correctly calculated
- [ ] Click receipt icon to view inline
- [ ] Filter expenses by property/date/type
- [ ] Upload lease document
- [ ] Browse documents by type
- [ ] Delete document
- [ ] Export expenses to CSV

---

## Existing Project Patterns to Follow

Based on the codebase:

1. **File Structure:**
   - Pages in `app/(dashboard)/[feature]/page.tsx`
   - Reusable components in `components/`
   - Use existing shadcn/ui components (Card, Button, Table, etc.)

2. **API Calls:**
   - Use existing `apiClient` pattern
   - Handle loading/error states
   - Use React hooks (useState, useEffect)

3. **Styling:**
   - TailwindCSS classes
   - Shadcn/ui components
   - Blue color scheme for positive values: `text-blue-700`
   - Red for negative: `text-red-700`

4. **Table Patterns:**
   - See `RentAnalysisTab.tsx` for table examples
   - Use sticky headers, sortable columns
   - Highlight rows on hover

---

## Reference Files in Codebase

- **Table Example:** `frontend/components/RentAnalysisTab.tsx` (lines 496-573)
- **Tab Pattern:** `frontend/app/(dashboard)/properties/[id]/page.tsx`
- **API Pattern:** `frontend/lib/api-client.ts`
- **Auth Pattern:** `frontend/lib/contexts/auth-context.tsx`

---

## Notes

- All backend APIs are tested and working
- SAS URLs expire after 24 hours (handled automatically)
- Documents are soft-deleted (kept in Iceberg metadata)
- Expense summary endpoint is optimized for CPA reporting
- File uploads limited to 10MB per file
- Supported formats: PDF, JPEG, PNG, GIF, WebP

---

## Current Status Summary

**BACKEND: 100% COMPLETE ✅**
**FRONTEND: 0% COMPLETE ⏳**

Next steps: Implement the 4 frontend components listed above, starting with API client functions and types.






