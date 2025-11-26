# Quick Local Testing Guide

## ✅ Current Status

- **Backend**: Running on http://localhost:8000 ✅
- **Frontend**: Running on http://localhost:3000 ✅
- **Services**: Both healthy

## 🧪 Quick Test Steps

### Option 1: Use Browser Console (Easiest)

1. **Open Frontend**: http://localhost:3000/expenses

2. **Open Browser Console** (F12 → Console tab)

3. **Get Auth Token** (run in console):
```javascript
// Register a new user
fetch('http://localhost:8000/api/v1/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'test@example.com',
    password: 'test123456',
    first_name: 'Test',
    last_name: 'User'
  })
})
.then(r => r.json())
.then(data => {
  if (data.access_token) {
    localStorage.setItem('auth_token', data.access_token);
    console.log('✅ Token saved! Refresh the page.');
    window.location.reload();
  } else {
    console.error('Registration failed:', data);
  }
});
```

4. **Refresh the page** - You should now see properties and be able to add expenses

### Option 2: Use Test Script

```bash
./test-local.sh
```

This will:
- Check services are running
- Try to register/login
- Give you the token to set in browser

## 🎯 Test Expense Creation

1. **Navigate to**: http://localhost:3000/expenses

2. **Click "+ Add Expense"**

3. **Fill in the form**:
   - Select a property (if you have properties)
   - Date: Today's date
   - Description: "Test expense"
   - Amount: 100.00
   - Expense Type: Maintenance
   - Upload a receipt (image or PDF)

4. **Click "Save Expense"**

5. **Verify**:
   - Expense appears in the list
   - Receipt link works (click "View")

## 🔍 Troubleshooting

### No Properties Showing
- Properties are user-scoped
- You need to create properties for your user first
- Or use the test data user ID: `11111111-1111-1111-1111-111111111111`

### Authentication Errors
- Check token is set: `localStorage.getItem('auth_token')`
- Token expires after 30 minutes - re-login if needed
- Check backend logs: `docker-compose logs backend`

### API Errors
- Check backend is running: `docker-compose ps`
- Check CORS: Backend should allow `http://localhost:3000`
- Check `.env.local` has correct `NEXT_PUBLIC_API_URL`

### File Upload Fails
- Check file size < 10MB
- Check file type (images or PDF only)
- Check Azure Storage credentials in backend `.env`

## 📝 Test Data

If you want to use existing test data:
- User ID: `11111111-1111-1111-1111-111111111111`
- Properties exist for this user
- You'll need to login/register with a user that matches this ID, OR
- Create new properties for your test user

## 🚀 Next Steps After Testing

Once local testing works:
1. Fix any issues found
2. Test file uploads work
3. Test receipt viewing works
4. Then proceed to Azure deployment

