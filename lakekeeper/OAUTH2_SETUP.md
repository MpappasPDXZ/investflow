# OAuth2 Setup for Lakekeeper with Azure AD

This guide walks through configuring OAuth2 authentication for Lakekeeper using Azure Active Directory (Azure AD).

## Prerequisites

1. Azure AD tenant
2. Azure AD App Registration permissions
3. Lakekeeper running and accessible

## Step 1: Create Azure AD App Registration

### App Registration 1: Lakekeeper API (Server Application)

This is the main application that Lakekeeper will validate tokens against.

1. **Go to Azure Portal** → Azure Active Directory → App registrations → New registration
2. **Name**: `Lakekeeper API`
3. **Supported account types**: Choose based on your needs (typically "Accounts in this organizational directory only")
4. **Redirect URI**: Leave blank (not needed for API-only app)
5. **Register**

6. **Configure API Permissions**:
   - Go to "Expose an API"
   - Set Application ID URI: `api://lakekeeper` (or your custom URI)
   - Add a scope: `lakekeeper` (or your preferred scope name)
   - Save

7. **Note the following values**:
   - **Application (client) ID**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - **Directory (tenant) ID**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - **Application ID URI**: `api://lakekeeper` (or your custom URI)

### App Registration 2: Backend Service Account (Machine User)

This is the service account that your backend will use to authenticate to Lakekeeper.

1. **Create another App Registration**:
   - **Name**: `Lakekeeper Backend Service`
   - **Supported account types**: Same as above
   - **Register**

2. **Create Client Secret**:
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Description: `Lakekeeper Backend Secret`
   - Expires: Choose appropriate expiration (24 months recommended)
   - **Copy the secret value immediately** (you won't see it again)

3. **Configure API Permissions**:
   - Go to "API permissions"
   - Click "Add a permission" → "My APIs"
   - Select "Lakekeeper API"
   - Select the `lakekeeper` scope (or your scope name)
   - Click "Add permissions"
   - **Grant admin consent** for your organization

4. **Note the following values**:
   - **Application (client) ID**: `yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy`
   - **Client Secret Value**: `your-secret-value-here` (from step 2)

### App Registration 3: Lakekeeper UI (Optional - for UI access)

If you want to use the Lakekeeper UI with OAuth2:

1. **Create another App Registration**:
   - **Name**: `Lakekeeper UI`
   - **Supported account types**: Same as above
   - **Redirect URI**: 
     - Type: Web
     - URI: `http://localhost:8181/callback` (for local) or your production URL

2. **Configure API Permissions**:
   - Same as Backend Service Account
   - Add `openid`, `profile`, `email` permissions from Microsoft Graph

3. **Note the following values**:
   - **Application (client) ID**: `zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz`

## Step 2: Configure Environment Variables

### For Lakekeeper Container

Add these to your `docker-compose.yml` or `.env` file:

```bash
# OAuth2/OIDC Configuration
LAKEKEEPER__OPENID_PROVIDER_URI=https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration
LAKEKEEPER__OPENID_AUDIENCE=api://lakekeeper  # Or your Application ID URI
LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS=  # Optional: additional issuers

# UI Configuration (if using Lakekeeper UI)
LAKEKEEPER__UI__OPENID_CLIENT_ID={UI_CLIENT_ID}  # App Registration 3
LAKEKEEPER__UI__OPENID_SCOPE=openid profile email lakekeeper
```

### For Backend Container

Add these to your `docker-compose.yml` or `.env` file:

```bash
# OAuth2 Client Credentials for Backend Service Account
LAKEKEEPER__OAUTH2__CLIENT_ID={BACKEND_CLIENT_ID}  # App Registration 2
LAKEKEEPER__OAUTH2__CLIENT_SECRET={BACKEND_CLIENT_SECRET}  # Secret from App Registration 2
LAKEKEEPER__OAUTH2__SCOPE=api://lakekeeper/.default  # Or your scope
LAKEKEEPER__OAUTH2__TENANT_ID={TENANT_ID}
LAKEKEEPER__OAUTH2__AUTHORITY=https://login.microsoftonline.com/{TENANT_ID}
```

## Step 3: Update Docker Compose

See the updated `docker-compose.yml` for the complete configuration.

## Step 4: Test the Configuration

1. Restart containers:
   ```bash
   docker-compose restart lakekeeper backend
   ```

2. Test backend authentication:
   ```bash
   curl http://localhost:8000/api/v1/lakekeeper/test/connection
   ```

3. Check Lakekeeper logs:
   ```bash
   docker-compose logs lakekeeper | grep -i "oauth\|openid\|auth"
   ```

## Troubleshooting

### Token Validation Errors

- **Invalid audience**: Ensure `LAKEKEEPER__OPENID_AUDIENCE` matches your Application ID URI
- **Invalid issuer**: Check that the issuer in the token matches Azure AD's issuer
- **Token expired**: Tokens typically expire after 1 hour; backend should refresh automatically

### Backend Cannot Get Token

- **Invalid client credentials**: Verify `CLIENT_ID` and `CLIENT_SECRET` are correct
- **Missing permissions**: Ensure the backend service account has the required API permissions
- **Wrong scope**: Verify the scope matches what's configured in Azure AD

### UI Login Issues

- **Redirect URI mismatch**: Ensure the redirect URI in Azure AD matches `LAKEKEEPER__UI__OPENID_REDIRECT_PATH`
- **Missing scopes**: Verify `LAKEKEEPER__UI__OPENID_SCOPE` includes required scopes

## Security Best Practices

1. **Use Azure Key Vault** for storing secrets instead of environment variables
2. **Rotate secrets regularly** (every 90 days recommended)
3. **Use managed identities** when running in Azure (instead of client secrets)
4. **Enable conditional access policies** in Azure AD
5. **Monitor authentication logs** for suspicious activity

## Alternative: Using Azure Managed Identity

If running in Azure (e.g., Azure Container Instances, Azure Kubernetes Service), you can use managed identities instead of client secrets:

```bash
# In Azure, use managed identity
LAKEKEEPER__ENABLE_AZURE_SYSTEM_CREDENTIALS=true
```

This eliminates the need for client secrets and is more secure.

