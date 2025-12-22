#!/bin/bash
# Fix production Lakekeeper encryption key to match local (NO WAREHOUSE DELETION)

set -e

echo "=========================================="
echo "🔧 FIXING ENCRYPTION KEY (NO DELETION)"
echo "=========================================="

RESOURCE_GROUP="investflow-rg"

# Step 1: Get local encryption key
echo ""
echo "📋 Step 1: Getting local encryption key from backend/.env..."
if [ ! -f "backend/.env" ]; then
  echo "   ❌ backend/.env file not found!"
  exit 1
fi

LOCAL_KEY=$(grep "^LAKEKEEPER__PG_ENCRYPTION_KEY=" backend/.env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)

if [ -z "$LOCAL_KEY" ]; then
  echo "   ❌ Local encryption key not found in backend/.env"
  exit 1
fi

echo "   ✅ Local key found (length: ${#LOCAL_KEY} characters)"

# Step 2: Get production encryption key
echo ""
echo "📋 Step 2: Getting production encryption key..."
PROD_KEY=$(az containerapp show \
  --name investflow-lakekeeper \
  --resource-group $RESOURCE_GROUP \
  --query "properties.template.containers[0].env[?name=='LAKEKEEPER__PG_ENCRYPTION_KEY'].value" \
  -o tsv 2>/dev/null)

if [ -z "$PROD_KEY" ]; then
  echo "   ⚠️  Production encryption key not set - will set it now"
else
  echo "   ✅ Production key found (length: ${#PROD_KEY} characters)"
fi

# Step 3: Compare and update if needed
echo ""
echo "📋 Step 3: Checking if keys match..."
if [ "$PROD_KEY" = "$LOCAL_KEY" ]; then
  echo "   ✅ Keys already match - no update needed"
  echo ""
  echo "   If warehouse still can't decrypt, the issue is elsewhere."
  exit 0
else
  echo "   ❌ Keys DO NOT MATCH - updating production to use local key"
  echo ""
  echo "   This will allow production to decrypt the existing warehouse credential."
fi

# Step 4: Update production encryption key
echo ""
echo "🔧 Step 4: Updating production Lakekeeper encryption key..."
az containerapp update \
  --name investflow-lakekeeper \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars LAKEKEEPER__PG_ENCRYPTION_KEY="$LOCAL_KEY" \
  > /dev/null

echo "   ✅ Encryption key updated"

# Step 5: Restart Lakekeeper to pick up new key
echo ""
echo "🔄 Step 5: Restarting production Lakekeeper..."
# Get the latest revision name
LATEST_REVISION=$(az containerapp revision list \
  --name investflow-lakekeeper \
  --resource-group $RESOURCE_GROUP \
  --query "[0].name" -o tsv)

if [ -n "$LATEST_REVISION" ]; then
  az containerapp revision restart \
    --name investflow-lakekeeper \
    --resource-group $RESOURCE_GROUP \
    --revision "$LATEST_REVISION" \
    > /dev/null
  echo "   ✅ Lakekeeper restarted (revision: $LATEST_REVISION)"
else
  echo "   ⚠️  Could not get revision name, but update should have triggered restart"
fi

echo "   Waiting 10 seconds for restart..."
sleep 10

# Step 6: Verify
echo ""
echo "🔍 Step 6: Verifying encryption key was set..."
VERIFY_KEY=$(az containerapp show \
  --name investflow-lakekeeper \
  --resource-group $RESOURCE_GROUP \
  --query "properties.template.containers[0].env[?name=='LAKEKEEPER__PG_ENCRYPTION_KEY'].value" \
  -o tsv)

if [ "$VERIFY_KEY" = "$LOCAL_KEY" ]; then
  echo "   ✅ Encryption key verified - matches local key"
else
  echo "   ❌ Verification failed - keys still don't match"
  exit 1
fi

# Step 7: Check health
echo ""
echo "🔍 Step 7: Checking Lakekeeper health..."
LAKEKEEPER_URL=$(az containerapp show \
  --name investflow-lakekeeper \
  --resource-group $RESOURCE_GROUP \
  --query "properties.configuration.ingress.fqdn" -o tsv)

HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "https://$LAKEKEEPER_URL/health" || echo "000")

if [ "$HEALTH" = "200" ]; then
  echo "   ✅ Lakekeeper is healthy"
else
  echo "   ⚠️  Health check returned: $HEALTH"
fi

echo ""
echo "=========================================="
echo "✅ ENCRYPTION KEY FIX COMPLETE"
echo "=========================================="
echo ""
echo "Production Lakekeeper now has the same encryption key as local."
echo "It should be able to decrypt the existing warehouse credential."
echo ""
echo "The warehouse was NOT deleted or modified - only the encryption key was updated."

