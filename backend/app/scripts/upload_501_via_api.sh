#!/bin/bash
# Upload comparables for 501 NE 67th St via API

set -e

# Configuration
API_URL="https://investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v1"
PROPERTY_ID="72144430-08ed-41de-b264-34af5181bd03"

# Prompt for credentials
echo "=== InvestFlow API Upload ==="
echo ""
read -p "Email: " EMAIL
read -sp "Password: " PASSWORD
echo ""
echo ""

# Authenticate and get token
echo "🔐 Authenticating..."
AUTH_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMAIL&password=$PASSWORD")

TOKEN=$(echo $AUTH_RESPONSE | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "❌ Authentication failed!"
  echo "Response: $AUTH_RESPONSE"
  exit 1
fi

echo "✅ Authenticated successfully!"
echo ""

# Upload comparables
echo "📤 Uploading comparables..."
echo ""

# Comp 1: 2403 NE Pursell Rd
echo "Uploading: 2403 NE Pursell Rd..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "2403 NE Pursell Rd",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 2,
    "square_feet": 1310,
    "asking_price": 1750,
    "has_solid_flooring": true,
    "has_quartz_granite": true,
    "garage_spaces": 1,
    "date_listed": "2025-08-28",
    "contacts": 34,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 2: 6105 N Forest Ave
echo "Uploading: 6105 N Forest Ave..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "6105 N Forest Ave",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 1,
    "square_feet": 1000,
    "asking_price": 1695,
    "has_fence": false,
    "has_solid_flooring": true,
    "has_quartz_granite": true,
    "has_ss_appliances": true,
    "has_shaker_cabinets": true,
    "has_washer_dryer": true,
    "garage_spaces": 1,
    "date_listed": "2025-10-03",
    "contacts": 22,
    "last_rented_price": 1625,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 3: 5612 N Euclid Ave
echo "Uploading: 5612 N Euclid Ave..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "5612 N Euclid Ave",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 2,
    "square_feet": 1225,
    "asking_price": 1910,
    "has_fence": false,
    "has_solid_flooring": true,
    "has_ss_appliances": true,
    "date_listed": "2025-11-21",
    "contacts": 5,
    "last_rented_price": 1525,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 4: 5707 N Woodland Ave
echo "Uploading: 5707 N Woodland Ave..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "5707 N Woodland Ave",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 1,
    "square_feet": 1225,
    "asking_price": 1450,
    "has_fence": true,
    "has_solid_flooring": true,
    "date_listed": "2025-08-26",
    "contacts": 112,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 5: 6017 N Howard Ave
echo "Uploading: 6017 N Howard Ave..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "6017 N Howard Ave",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 2,
    "square_feet": 1400,
    "asking_price": 2000,
    "has_fence": false,
    "has_ss_appliances": true,
    "garage_spaces": 2,
    "date_listed": "2025-12-10",
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 6: 5700 N Highland Ave
echo "Uploading: 5700 N Highland Ave..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "5700 N Highland Ave",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 1,
    "square_feet": 923,
    "asking_price": 1570,
    "has_fence": false,
    "has_solid_flooring": true,
    "has_quartz_granite": true,
    "has_ss_appliances": true,
    "has_shaker_cabinets": true,
    "garage_spaces": 1,
    "date_listed": "2025-09-27",
    "contacts": 53,
    "last_rented_price": 1520,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 7: 5708 N Euclid Ave
echo "Uploading: 5708 N Euclid Ave..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "5708 N Euclid Ave",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 1,
    "square_feet": 925,
    "asking_price": 1550,
    "has_fence": false,
    "has_solid_flooring": true,
    "garage_spaces": 1,
    "date_listed": "2025-10-23",
    "contacts": 30,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 8: 2701 NE 67th Ter
echo "Uploading: 2701 NE 67th Ter..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "2701 NE 67th Ter",
    "city": "Kansas City",
    "state": "MO",
    "zip_code": "64119",
    "property_type": "House",
    "bedrooms": 4,
    "bathrooms": 2,
    "square_feet": 1300,
    "asking_price": 1900,
    "has_fence": true,
    "has_solid_flooring": true,
    "garage_spaces": 2,
    "date_listed": "2025-09-14",
    "contacts": 76,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Comp 9: 5507 N Lydia Ave
echo "Uploading: 5507 N Lydia Ave..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "5507 N Lydia Ave",
    "city": "Gladstone",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 1.5,
    "square_feet": 1075,
    "asking_price": 1695,
    "has_solid_flooring": true,
    "garage_spaces": 1,
    "date_listed": "2025-11-24",
    "contacts": 15,
    "last_rented_price": 1595,
    "is_subject_property": false
  }' | jq -r '.id' && echo "✓"

# Subject Property: 501 NE 67th St
echo "Uploading: 501 NE 67th St (SUBJECT)..."
curl -s -X POST "$API_URL/comparables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "'$PROPERTY_ID'",
    "address": "501 NE 67th St",
    "city": "Kansas City",
    "state": "MO",
    "zip_code": "64118",
    "property_type": "House",
    "bedrooms": 3,
    "bathrooms": 1,
    "square_feet": 988,
    "asking_price": 1595,
    "has_fence": true,
    "has_solid_flooring": true,
    "has_quartz_granite": true,
    "has_ss_appliances": true,
    "has_shaker_cabinets": true,
    "has_washer_dryer": true,
    "garage_spaces": 2,
    "date_listed": "2024-12-01",
    "is_subject_property": true,
    "notes": "Subject property"
  }' | jq -r '.id' && echo "✓"

echo ""
echo "✅ Successfully uploaded 10 comparables!"
echo ""
echo "View at: https://investflow-frontend.yellowsky-ca466dfe.eastus.azurecontainerapps.io/properties/$PROPERTY_ID"

