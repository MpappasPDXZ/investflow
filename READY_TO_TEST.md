# ✅ Ready to Test Locally!

## Status

- ✅ **Backend**: Running on http://localhost:8000
- ✅ **Frontend**: Running on http://localhost:3000  
- ✅ **Users Table**: Fixed and working
- ✅ **Registration**: Working

## 🚀 Quick Start

### Step 1: Get Auth Token

**Open browser console** (F12 → Console) on http://localhost:3000/expenses and run:

```javascript
// Register and auto-set token
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
    console.log('✅ Token saved!');
    window.location.reload();
  } else {
    console.error('Failed:', data);
  }
});
```

### Step 2: Test Expense Creation

1. **Refresh the page** after setting token
2. **Click "+ Add Expense"**
3. **Fill the form**:
   - Property: (will be empty - that's OK, you can still create expenses)
   - Date: Today
   - Description: "Test expense with receipt"
   - Amount: 100.00
   - Expense Type: Maintenance
   - **Upload a receipt** (image or PDF - try a small test file)
4. **Click "Save Expense"**
5. **Verify**:
   - Expense appears in the list
   - Receipt link shows "View Image" or "View PDF"
   - Click it to verify file upload worked

## 🧪 Test Checklist

- [x] Backend running
- [x] Frontend running  
- [x] User registration works
- [ ] Token stored in browser
- [ ] Properties list loads (may be empty)
- [ ] Can create expense
- [ ] Can upload receipt
- [ ] Expense appears in list
- [ ] Receipt link works
- [ ] Can view/download receipt

## 📝 Notes

1. **Properties**: If no properties show, you can still create expenses. The property_id field will be required, so you may need to create a property first, OR we can make it optional for testing.

2. **File Upload**: 
   - Max size: 10MB
   - Types: Images (jpg, png, gif, webp) or PDF
   - Files stored in Azure Blob Storage

3. **Authentication**: Token expires after 30 minutes. Re-run the registration code to get a new token.

## 🐛 If Something Doesn't Work

### No Properties Showing
- This is OK - you can still test expense creation
- Or create a property via API first

### Can't Upload File
- Check file size < 10MB
- Check file type (images or PDF)
- Check backend logs: `docker-compose logs backend`

### API Errors
- Check token is set: `localStorage.getItem('auth_token')`
- Check backend is running: `docker-compose ps`
- Check CORS settings

## 🎯 What to Test

1. **Expense Creation**: Create an expense with all fields
2. **File Upload**: Upload a receipt (image or PDF)
3. **Expense List**: Verify expense appears
4. **Receipt Viewing**: Click receipt link and verify file opens
5. **Filtering**: Filter expenses by property (if you have properties)

## ✅ Once Testing Works

After you verify everything works locally:
1. Fix any issues found
2. Test with multiple expenses
3. Test with different file types
4. Then we can deploy to Azure!

