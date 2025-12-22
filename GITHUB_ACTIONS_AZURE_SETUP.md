# GitHub Actions Azure Authentication Setup

## Problem
GitHub Actions needs to authenticate to Azure to:
- Push Docker images to Azure Container Registry (ACR)
- Deploy to Azure Container Apps
- Update environment variables

## Solution: Create Azure Service Principal

### Step 1: Create Service Principal

Run this command (replace with your subscription ID if different):

```bash
az ad sp create-for-rbac \
  --name "github-actions-investflow" \
  --role contributor \
  --scopes /subscriptions/ca208856-aeee-4327-95b7-d132da93df78/resourceGroups/investflow-rg \
  --sdk-auth
```

**Output will look like:**
```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "ca208856-aeee-4327-95b7-d132da93df78",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

### Step 2: Grant ACR Permissions

The service principal needs permission to push to ACR:

```bash
# Get ACR resource ID
ACR_ID=$(az acr show --name investflowregistry --resource-group investflow-rg --query id --output tsv)

# Get service principal client ID (from Step 1 output)
SP_CLIENT_ID="<clientId-from-step-1>"

# Grant AcrPush role
az role assignment create \
  --assignee $SP_CLIENT_ID \
  --role AcrPush \
  --scope $ACR_ID
```

### Step 3: Add to GitHub Secrets

1. Go to your GitHub repository: `https://github.com/MpappasPDXZ/investflow`
2. Navigate to: **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `AZURE_CREDENTIALS`
5. Value: Paste the **entire JSON output** from Step 1
6. Click **Add secret**

### Step 4: Verify

After adding the secret, push a commit to trigger the workflow:

```bash
git commit --allow-empty -m "Test GitHub Actions deployment"
git push origin main
```

Then check the Actions tab: `https://github.com/MpappasPDXZ/investflow/actions`

---

## Alternative: Use Existing Service Principal

If you already have a service principal, you can use it:

```bash
# List existing service principals
az ad sp list --display-name "github-actions-investflow" --query "[].{displayName:displayName, appId:appId}" -o table

# If it exists, create a new password/secret for it
az ad sp credential reset --name "github-actions-investflow" --sdk-auth
```

---

## Troubleshooting

### Error: "The subscription is not registered to use namespace 'Microsoft.ContainerRegistry'"
```bash
az provider register --namespace Microsoft.ContainerRegistry
```

### Error: "Insufficient privileges to complete the operation"
Make sure you're running as a user with Owner or Contributor role on the subscription.

### Error: "Authentication failed"
- Verify the JSON in GitHub secrets is valid
- Check that the service principal hasn't expired
- Ensure the service principal has the correct role assignments

---

## Security Notes

⚠️ **Important:**
- The service principal has Contributor access to your resource group
- Keep the `clientSecret` secure - never commit it to git
- Rotate credentials periodically (every 90 days recommended)
- If compromised, delete and recreate the service principal immediately

