#!/bin/bash
# Quick test script for local testing

echo "🧪 Testing InvestFlow Locally"
echo "================================"
echo ""

# Check backend
echo "1. Checking backend..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "   ✅ Backend is running on http://localhost:8000"
else
    echo "   ❌ Backend is not running. Start it with: cd backend && docker-compose up -d"
    exit 1
fi

# Check frontend
echo ""
echo "2. Checking frontend..."
if curl -s http://localhost:3000 > /dev/null; then
    echo "   ✅ Frontend is running on http://localhost:3000"
else
    echo "   ❌ Frontend is not running. Start it with: cd frontend && npm run dev"
    exit 1
fi

# Try to register a test user
echo ""
echo "3. Registering test user..."
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123456",
    "first_name": "Test",
    "last_name": "User"
  }')

if echo "$REGISTER_RESPONSE" | grep -q "access_token"; then
    TOKEN=$(echo "$REGISTER_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
    echo "   ✅ User registered successfully"
    echo "   📝 Token: ${TOKEN:0:50}..."
    echo ""
    echo "4. Setting token in browser..."
    echo "   Open browser console (F12) and run:"
    echo "   localStorage.setItem('auth_token', '$TOKEN');"
    echo ""
    echo "5. Then navigate to: http://localhost:3000/expenses"
else
    echo "   ⚠️  Registration failed (user may already exist)"
    echo "   Trying login instead..."
    
    LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d '{
        "email": "test@example.com",
        "password": "test123456"
      }')
    
    if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
        TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
        echo "   ✅ Login successful"
        echo "   📝 Token: ${TOKEN:0:50}..."
        echo ""
        echo "4. Setting token in browser..."
        echo "   Open browser console (F12) and run:"
        echo "   localStorage.setItem('auth_token', '$TOKEN');"
        echo ""
        echo "5. Then navigate to: http://localhost:3000/expenses"
    else
        echo "   ❌ Login failed. Check backend logs."
        echo "   Response: $LOGIN_RESPONSE"
    fi
fi

echo ""
echo "================================"
echo "✅ Testing setup complete!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:3000/expenses in your browser"
echo "2. Set the auth token in browser console (see above)"
echo "3. Refresh the page"
echo "4. Click '+ Add Expense' to test the form"

