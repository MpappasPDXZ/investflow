# Production Authentication Configuration

## Authentication Flow Overview

Your application has **three separate authentication layers**:

1. **Frontend → Backend**: JWT tokens (email/password login)
2. **Backend → Lakekeeper**: OAuth2 Client Credentials (Azure AD)
3. **Lakekeeper UI**: OIDC (Azure AD) - separate from backend

## 1. Frontend → Backend Authentication

### How It Works:
- User logs in via `/api/v1/auth/login` with email/password
- Backend validates against `users` table in Iceberg
- Backend returns JWT token signed with `SECRET_KEY`
- Frontend stores token in localStorage and sends in `Authorization: Bearer <token>` header

### Production Configuration Needed:

**Backend Container App Environment Variables:**
```bash
# JWT Secret (CRITICAL - must be strong and unique)
SECRET_KEY=<generate-a-strong-random-32+char-secret>

# CORS - Allow production frontend
CORS_ORIGINS=https://investflow-frontend.yellowsky-ca466dfe.eastus.azurecontainerapps.io

# Token expiration (8 hours default)
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

**Status**: ✅ This should work automatically once CORS is configured

---

## 2. Backend → Lakekeeper Authentication

### How It Works:
- Backend uses **OAuth2 Client Credentials** flow to get Azure AD token
- Token is used to authenticate all requests to Lakekeeper REST API
- Configured in `backend/app/core/iceberg.py` (lines 22-38)

### Production Configuration Needed:

**Backend Container App Environment Variables:**
```bash
# Lakekeeper URL (ALREADY SET in GitHub Actions)
LAKEKEEPER__BASE_URI=https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io

# OAuth2 Client Credentials for Lakekeeper
LAKEKEEPER__OAUTH2__CLIENT_ID=2f43977e-7c3d-478f-86b0-f72b82e869dd
LAKEKEEPER__OAUTH2__CLIENT_SECRET=<your-client-secret>  # Store as secret!
LAKEKEEPER__OAUTH2__TENANT_ID=479bc30b-030f-4a2e-8ea2-67f549b32f5e
LAKEKEEPER__OAUTH2__SCOPE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default

# Warehouse name
LAKEKEEPER__WAREHOUSE_NAME=lakekeeper
```

**Status**: ⚠️ **MUST BE CONFIGURED** - Currently only `LAKEKEEPER__BASE_URI` is set in GitHub Actions

---

## 3. Lakekeeper UI Authentication

### How It Works:
- Lakekeeper has its own OIDC configuration for its web UI
- This is separate from backend authentication
- Users access Lakekeeper UI directly (if needed)

### Production Configuration:

**Lakekeeper Container App Environment Variables:**
```bash
LAKEKEEPER__OPENID_PROVIDER_URI=https://login.microsoftonline.com/479bc30b-030f-4a2e-8ea2-67f549b32f5e/v2.0
LAKEKEEPER__OPENID_AUDIENCE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7
LAKEKEEPER__OAUTH2__CLIENT_ID=2f43977e-7c3d-478f-86b0-f72b82e869dd
LAKEKEEPER__OAUTH2__CLIENT_SECRET=<your-client-secret>
LAKEKEEPER__OAUTH2__TENANT_ID=479bc30b-030f-4a2e-8ea2-67f549b32f5e
LAKEKEEPER__OAUTH2__SCOPE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default
```

**Status**: ⚠️ **MUST BE CONFIGURED** in Lakekeeper Container App

---

## Complete Production Setup Commands

### Backend Container App

```bash
# Set environment variables
az containerapp update \
  --name investflow-backend \
  --resource-group investflow-rg \
  --set-env-vars \
    CORS_ORIGINS=https://investflow-frontend.yellowsky-ca466dfe.eastus.azurecontainerapps.io \
    LAKEKEEPER__BASE_URI=https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io \
    LAKEKEEPER__WAREHOUSE_NAME=lakekeeper \
    LAKEKEEPER__OAUTH2__CLIENT_ID=2f43977e-7c3d-478f-86b0-f72b82e869dd \
    LAKEKEEPER__OAUTH2__TENANT_ID=479bc30b-030f-4a2e-8ea2-67f549b32f5e \
    LAKEKEEPER__OAUTH2__SCOPE="api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default"

# Set secrets (store sensitive values)
az containerapp update \
  --name investflow-backend \
  --resource-group investflow-rg \
  --secrets \
    jwt-secret=<generate-strong-secret> \
    lakekeeper-oauth-secret=<your-oauth2-client-secret> \
    azure-storage-key=<your-azure-storage-key> \
    pg-encryption-key=<your-encryption-key>

# Reference secrets in env vars
az containerapp update \
  --name investflow-backend \
  --resource-group investflow-rg \
  --set-env-vars \
    SECRET_KEY=secretref:jwt-secret \
    LAKEKEEPER__OAUTH2__CLIENT_SECRET=secretref:lakekeeper-oauth-secret \
    AZURE_STORAGE_ACCOUNT_KEY=secretref:azure-storage-key \
    LAKEKEEPER__PG_ENCRYPTION_KEY=secretref:pg-encryption-key
```

### Lakekeeper Container App

```bash
az containerapp update \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --set-env-vars \
    LAKEKEEPER__OPENID_PROVIDER_URI=https://login.microsoftonline.com/479bc30b-030f-4a2e-8ea2-67f549b32f5e/v2.0 \
    LAKEKEEPER__OPENID_AUDIENCE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7 \
    LAKEKEEPER__OAUTH2__CLIENT_ID=2f43977e-7c3d-478f-86b0-f72b82e869dd \
    LAKEKEEPER__OAUTH2__TENANT_ID=479bc30b-030f-4a2e-8ea2-67f549b32f5e \
    LAKEKEEPER__OAUTH2__SCOPE="api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default"

# Set secrets
az containerapp update \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --secrets \
    oauth-secret=<your-oauth2-client-secret> \
    pg-encryption-key=<your-encryption-key>

# Reference secrets
az containerapp update \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --set-env-vars \
    LAKEKEEPER__OAUTH2__CLIENT_SECRET=secretref:oauth-secret \
    LAKEKEEPER__PG_ENCRYPTION_KEY=secretref:pg-encryption-key
```

---

## What's Currently Configured

✅ **GitHub Actions** sets `LAKEKEEPER__BASE_URI` automatically  
❌ **Missing**: OAuth2 credentials for backend → Lakekeeper  
❌ **Missing**: CORS configuration for production frontend  
❌ **Missing**: JWT secret for production  
❌ **Missing**: Lakekeeper OIDC configuration  

---

## Testing Authentication

### Test Frontend → Backend:
```bash
curl -X POST https://investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpassword"}'
```

### Test Backend → Lakekeeper:
```bash
# This happens automatically when backend tries to read/write Iceberg tables
# Check backend logs for authentication errors
```

---

## Important Notes

1. **OAuth2 Client Secret**: Must be the same Azure AD App Registration secret used by both backend and Lakekeeper
2. **JWT Secret**: Generate a strong random secret (32+ characters) - different from OAuth2 secret
3. **CORS**: Must include production frontend URL or requests will be blocked
4. **Lakekeeper Encryption Key**: Must match between backend and Lakekeeper for secret decryption

