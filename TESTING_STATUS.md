# Local Testing Status

## ✅ Services Running

- **Backend**: http://localhost:8000 ✅
- **Frontend**: http://localhost:3000 ✅

## 🧪 Testing Instructions

### Step 1: Get Authentication Token

**Option A: Browser Console** (Recommended)
1. Open http://localhost:3000/expenses
2. Open browser console (F12)
3. Run this code:
```javascript
fetch('http://localhost:8000/api/v1/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'test' + Date.now() + '@example.com',
    password: 'test123456',
    first_name: 'Test',
    last_name: 'User'
  })
})
.then(r => r.json())
.then(data => {
  if (data.access_token) {
    localStorage.setItem('auth_token', data.access_token);
    alert('✅ Token saved! Refreshing page...');
    window.location.reload();
  } else {
    console.error('Failed:', data);
  }
});
```

**Option B: Command Line**
```bash
# Register
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test'$(date +%s)'@example.com","password":"test123456","first_name":"Test","last_name":"User"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

echo "Token: $TOKEN"
# Then set in browser: localStorage.setItem('auth_token', '$TOKEN');
```

### Step 2: Test Expense Creation

1. **Navigate to**: http://localhost:3000/expenses
2. **Click "+ Add Expense"**
3. **Fill form**:
   - Property: (will be empty if no properties exist - that's OK for now)
   - Date: Today
   - Description: "Test expense"
   - Amount: 100.00
   - Type: Maintenance
   - Upload a receipt (image or PDF)
4. **Click "Save Expense"**

### Step 3: Verify

- Expense should appear in the list
- Receipt link should work
- File should be viewable

## 🔧 Current Issues

### Users Table
- Users are stored in PostgreSQL (for fast auth lookups)
- Table should auto-create on first request
- If registration fails, check backend logs

### Properties
- Properties are in Iceberg tables
- If no properties show, you need to create them first
- Or use test data user ID: `11111111-1111-1111-1111-111111111111`

## 📊 Test Checklist

- [ ] Backend health check works
- [ ] Frontend loads
- [ ] Can register/login user
- [ ] Token stored in localStorage
- [ ] Properties list loads (or shows empty)
- [ ] Can create expense
- [ ] Can upload receipt
- [ ] Expense appears in list
- [ ] Receipt link works
- [ ] Can view/download receipt

## 🐛 Debugging

### Check Backend Logs
```bash
cd backend
docker-compose logs -f backend
```

### Check Frontend Logs
```bash
# Frontend logs are in the terminal where you ran `npm run dev`
# Or check: /tmp/frontend-dev.log
```

### Test API Directly
```bash
# Health check
curl http://localhost:8000/health

# Register (get token)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123456","first_name":"Test","last_name":"User"}'

# List properties (with token)
curl http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## ✅ Next Steps

Once local testing works:
1. Verify expense creation works
2. Verify file upload works
3. Verify receipt viewing works
4. Then proceed to Azure deployment

