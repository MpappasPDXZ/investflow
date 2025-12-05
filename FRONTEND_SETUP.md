# Frontend Setup - Expense Logging with File Upload

## ✅ Completed

### Backend
1. **Expense Service** (`backend/app/services/expense_service.py`)
   - CRUD operations using PyIceberg
   - Filtering by property and user
   
2. **Document Service** (`backend/app/services/document_service.py`)
   - Upload to Azure Blob Storage
   - Generate signed download URLs
   - Store metadata in Iceberg `document_storage` table

3. **API Endpoints**
   - `POST /api/v1/expenses` - Create expense
   - `POST /api/v1/expenses/with-receipt` - Create expense with file upload
   - `GET /api/v1/expenses` - List expenses (with property filter)
   - `GET /api/v1/expenses/{id}` - Get expense
   - `PUT /api/v1/expenses/{id}` - Update expense
   - `DELETE /api/v1/expenses/{id}` - Delete expense
   - `GET /api/v1/expenses/{id}/receipt` - Get receipt download URL
   - `POST /api/v1/documents/upload` - Upload document
   - `GET /api/v1/documents/{id}` - Get document metadata
   - `GET /api/v1/documents/{id}/download` - Get download URL

### Frontend
1. **API Client** (`frontend/lib/api-client.ts`)
   - Handles authentication tokens
   - Supports file uploads
   
2. **React Query Hooks**
   - `useExpenses()` - List expenses
   - `useExpense()` - Get single expense
   - `useCreateExpenseWithReceipt()` - Create expense with file
   - `useProperties()` - List properties

3. **Pages**
   - `/expenses` - Expense list and form
   - Home page with navigation

4. **Components**
   - `ReceiptViewer` - Displays receipt download links

## 🧪 Testing Locally

### Prerequisites
1. Backend running on `http://localhost:8000`
2. Frontend running on `http://localhost:3000`
3. User authenticated (token in localStorage as `auth_token`)

### Steps
1. **Start Backend**:
   ```bash
   cd backend
   docker-compose up -d
   ```

2. **Start Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Set Environment Variables** (frontend/.env.local):
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. **Test Flow**:
   - Navigate to `/expenses`
   - Click "+ Add Expense"
   - Fill in form (property, date, description, amount, type)
   - Upload a receipt (image or PDF)
   - Submit
   - Verify expense appears in list
   - Click "View" on receipt to verify file upload

### Authentication
Currently, the app expects a JWT token in `localStorage.getItem('auth_token')`. 

For testing, you can:
1. Use the `/api/v1/auth/register` or `/api/v1/auth/login` endpoints
2. Store the token: `localStorage.setItem('auth_token', 'your-token-here')`

## 🚀 Deployment to Azure

### Backend Deployment

1. **Build Docker Image**:
   ```bash
   cd backend
   docker build -t investflow-backend:latest .
   ```

2. **Push to Azure Container Registry**:
   ```bash
   az acr login --name investflowregistry
   docker tag investflow-backend:latest investflowregistry.azurecr.io/investflow-backend:latest
   docker push investflowregistry.azurecr.io/investflow-backend:latest
   ```

3. **Deploy to Container App**:
   ```bash
   az containerapp update \
     --name investflow-backend \
     --resource-group investflow-rg \
     --image investflowregistry.azurecr.io/investflow-backend:latest \
     --set-env-vars "POSTGRES_HOST=..." "AZURE_STORAGE_ACCOUNT_KEY=..." \
     # ... other env vars
   ```

### Frontend Deployment

1. **Build Docker Image**:
   ```bash
   cd frontend
   docker build -t investflow-frontend:latest .
   ```

2. **Push to ACR**:
   ```bash
   docker tag investflow-frontend:latest investflowregistry.azurecr.io/investflow-frontend:latest
   docker push investflowregistry.azurecr.io/investflow-frontend:latest
   ```

3. **Deploy to Container App**:
   ```bash
   az containerapp update \
     --name investflow-frontend \
     --resource-group investflow-rg \
     --image investflowregistry.azurecr.io/investflow-frontend:latest \
     --set-env-vars "NEXT_PUBLIC_API_URL=https://your-backend-url.azurecontainerapps.io"
   ```

### Environment Variables Needed

**Backend**:
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY`, `AZURE_STORAGE_CONTAINER_NAME`
- `SECRET_KEY`, `CORS_ORIGINS` (should include frontend URL)
- Lakekeeper OAuth2 variables

**Frontend**:
- `NEXT_PUBLIC_API_URL` - Backend API URL

## 📝 Notes

1. **File Upload**: Currently accepts images (jpeg, jpg, png, gif, webp) and PDFs, max 10MB
2. **Storage**: Files stored in Azure Blob Storage at `{user_id}/{document_type}/{year}/{month}/{filename}`
3. **Download URLs**: Signed URLs expire after 1 hour
4. **Authentication**: Currently uses localStorage for token storage (consider httpOnly cookies for production)

## 🔧 Next Steps

1. Add authentication UI (login/register pages)
2. Add property management UI
3. Add expense editing/deletion
4. Improve error handling and loading states
5. Add image preview in expense list
6. Add pagination for large expense lists






