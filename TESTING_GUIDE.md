# Local Testing Guide

## Prerequisites

1. **Backend running**: `cd backend && docker-compose up -d`
2. **Frontend dependencies installed**: `cd frontend && npm install`
3. **Environment configured**: Frontend `.env.local` exists

## Step 1: Start Services

### Backend (already running)
```bash
cd backend
docker-compose up -d
# Check status
docker-compose ps
# View logs
docker-compose logs -f backend
```

### Frontend
```bash
cd frontend
npm run dev
# Should start on http://localhost:3000
```

## Step 2: Get Authentication Token

### Option A: Register New User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123456",
    "first_name": "Test",
    "last_name": "User"
  }'
```

### Option B: Login (if user exists)
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123456"
  }'
```

Response will include:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## Step 3: Set Token in Browser

1. Open browser console (F12)
2. Run:
```javascript
localStorage.setItem('auth_token', 'YOUR_TOKEN_HERE');
```
3. Refresh the page

## Step 4: Test Expense Creation

1. Navigate to `http://localhost:3000/expenses`
2. Click "+ Add Expense"
3. Fill in the form:
   - Select a property
   - Enter date, description, amount
   - Select expense type
   - Upload a receipt (image or PDF)
4. Click "Save Expense"
5. Verify expense appears in the list
6. Click "View" on receipt to verify file upload

## Step 5: Test API Directly

### List Properties
```bash
curl -X GET http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Create Expense
```bash
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "description": "Test expense",
    "date": "2024-01-15",
    "amount": "100.00",
    "expense_type": "maintenance",
    "is_planned": false
  }'
```

### Create Expense with Receipt
```bash
curl -X POST http://localhost:8000/api/v1/expenses/with-receipt \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "property_id=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" \
  -F "description=Test expense with receipt" \
  -F "date=2024-01-15" \
  -F "amount=150.00" \
  -F "expense_type=maintenance" \
  -F "file=@/path/to/receipt.jpg"
```

## Troubleshooting

### Backend not responding
- Check: `docker-compose ps`
- Restart: `docker-compose restart backend`
- Logs: `docker-compose logs backend`

### Frontend can't connect to backend
- Check `.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Check backend is running on port 8000
- Check CORS settings in backend

### Authentication errors
- Verify token is set: `localStorage.getItem('auth_token')`
- Check token hasn't expired (30 minutes default)
- Re-login to get new token

### File upload fails
- Check file size < 10MB
- Check file type (images or PDF only)
- Check Azure Storage credentials in backend `.env`

### No properties showing
- Properties are user-scoped
- Use the user_id from your auth token
- Check properties exist in Iceberg table for that user

## Test Data

From `create_data.py`, test user:
- User ID: `11111111-1111-1111-1111-111111111111`
- Email: `john.doe@example.com`
- Properties: 2 properties exist

To use test data, you may need to:
1. Register/login with matching user_id, OR
2. Create properties for your test user

