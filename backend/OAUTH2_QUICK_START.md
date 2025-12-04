# OAuth2 Quick Start Guide

This guide helps you quickly configure OAuth2 for Lakekeeper using Azure AD.

## Prerequisites

Before running the configuration script, you need to create Azure AD App Registrations. See `lakekeeper/OAUTH2_SETUP.md` for detailed instructions.

**Quick checklist:**
- [ ] Created "Lakekeeper API" App Registration
- [ ] Created "Backend Service Account" App Registration  
- [ ] Created client secret for Backend Service Account
- [ ] Granted API permissions and admin consent

## Option 1: Interactive Script (Recommended)

Run the interactive configuration script:

```bash
cd backend
./configure_oauth2.sh
```

The script will:
1. Ask for your Azure AD Tenant ID
2. Ask for Lakekeeper API configuration
3. Ask for Backend Service Account credentials
4. Optionally configure UI authentication
5. Generate and update your `.env` file

## Option 2: Manual Configuration

If you prefer to configure manually, add these variables to your `.env` file:

```bash
# Lakekeeper OAuth2 Configuration
LAKEKEEPER__OPENID_PROVIDER_URI=https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration
LAKEKEEPER__OPENID_AUDIENCE=api://lakekeeper

# Backend OAuth2 Configuration
LAKEKEEPER__OAUTH2__CLIENT_ID={BACKEND_CLIENT_ID}
LAKEKEEPER__OAUTH2__CLIENT_SECRET={BACKEND_CLIENT_SECRET}
LAKEKEEPER__OAUTH2__TENANT_ID={TENANT_ID}
LAKEKEEPER__OAUTH2__SCOPE=api://lakekeeper/.default
```

Replace:
- `{TENANT_ID}` - Your Azure AD Tenant ID
- `{BACKEND_CLIENT_ID}` - Backend Service Account Application ID
- `{BACKEND_CLIENT_SECRET}` - Backend Service Account Client Secret

## Finding Your Azure AD Values

### Tenant ID
1. Go to Azure Portal → Azure Active Directory
2. Click "Overview"
3. Copy the "Tenant ID"

### Application IDs and Secrets
1. Go to Azure Portal → Azure Active Directory → App registrations
2. Click on your app registration
3. Copy the "Application (client) ID"
4. For secrets: Go to "Certificates & secrets" → Copy the secret value

### Application ID URI (Audience)
1. Go to your "Lakekeeper API" App Registration
2. Click "Expose an API"
3. Copy the "Application ID URI" (e.g., `api://lakekeeper`)

## Verifying Configuration

After configuring, restart your containers:

```bash
docker-compose restart lakekeeper backend
```

Test the configuration:

```bash
# Test backend connection to Lakekeeper
curl http://localhost:8000/api/v1/lakekeeper/test/connection

# Check OAuth2 token acquisition
curl http://localhost:8000/api/v1/lakekeeper/test/integration
```

## Troubleshooting

### "Invalid client" error
- Verify `LAKEKEEPER__OAUTH2__CLIENT_ID` and `LAKEKEEPER__OAUTH2__CLIENT_SECRET` are correct
- Check that the client secret hasn't expired

### "Invalid audience" error
- Verify `LAKEKEEPER__OPENID_AUDIENCE` matches your Application ID URI
- Check that the backend service account has permission to use the scope

### "Insufficient permissions" error
- Ensure admin consent has been granted for the API permissions
- Verify the backend service account has the correct scope assigned

### Token not refreshing
- Check backend logs: `docker-compose logs backend | grep -i oauth`
- Verify OAuth2 configuration is correct
- Check network connectivity to Azure AD

## Security Notes

⚠️ **Important Security Considerations:**

1. **Never commit `.env` file** - It contains sensitive secrets
2. **Use Azure Key Vault** in production instead of environment variables
3. **Rotate secrets regularly** - Client secrets should be rotated every 90 days
4. **Use managed identities** when running in Azure (more secure than client secrets)

## Next Steps

Once OAuth2 is configured:
- ✅ Backend will automatically authenticate to Lakekeeper
- ✅ DuckDB will use OAuth2 for REST catalog access
- ✅ All API calls will be secured with OAuth2 tokens
- ✅ Tokens will automatically refresh before expiration

For production deployment, consider:
- Using Azure Key Vault for secret management
- Enabling Azure Managed Identity
- Setting up monitoring and alerting for authentication failures





