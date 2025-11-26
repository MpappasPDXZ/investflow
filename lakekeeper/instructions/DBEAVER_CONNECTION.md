# DBeaver Connection Settings for Azure PostgreSQL

## Connection Details

### Basic Settings

1. **Database Type**: PostgreSQL
2. **Host**: `if-postgres.postgres.database.azure.com`
3. **Port**: `5432`
4. **Database**: `investflow`
5. **Username**: `pgadmin`
6. **Password**: (Your `POSTGRES_PASSWORD` from `.env` file)

### SSL Settings (REQUIRED for Azure PostgreSQL)

Azure PostgreSQL requires SSL connections. Configure these settings:

1. **SSL Mode**: `Require` or `Verify-CA`
2. **SSL Factory**: `org.postgresql.ssl.DefaultJavaSSLFactory` (default)
3. **SSL Root Certificate**: (Optional - Azure uses public CA certificates)

### Step-by-Step DBeaver Setup

1. **Open DBeaver**
2. **New Database Connection** → PostgreSQL
3. **Main Tab**:
   - **Host**: `if-postgres.postgres.database.azure.com`
   - **Port**: `5432`
   - **Database**: `investflow`
   - **Username**: `pgadmin`
   - **Password**: (Enter your password)
   - **Show all databases**: ✅ Check this

4. **SSL Tab**:
   - **Use SSL**: ✅ Check this
   - **SSL Mode**: Select `require` from dropdown
   - **SSL Factory**: Leave default (`org.postgresql.ssl.DefaultJavaSSLFactory`)

5. **Test Connection** → Should show "Connected"

### Connection String Format

If you need to use a connection string elsewhere:

```
postgresql://pgadmin:YOUR_PASSWORD@if-postgres.postgres.database.azure.com:5432/investflow?sslmode=require
```

### Important Notes

- **SSL is REQUIRED** - Azure PostgreSQL will reject non-SSL connections
- **Firewall Rules** - Make sure your IP is allowed in Azure PostgreSQL firewall rules
- **Password** - Use the same password from your `backend/.env` file (`POSTGRES_PASSWORD`)

### Troubleshooting

**Error: "Connection refused"**
- Check firewall rules in Azure Portal → PostgreSQL server → Networking
- Add your IP address to allowed IPs

**Error: "SSL required"**
- Make sure "Use SSL" is checked in DBeaver
- Set SSL Mode to `require`

**Error: "Authentication failed"**
- Verify username is `pgadmin` (not `pgadmin@if-postgres`)
- Check password matches `POSTGRES_PASSWORD` in `.env`

### Finding Your Password

Your password is stored in:
- `backend/.env` file → `POSTGRES_PASSWORD=...`
- Or Azure Key Vault (if configured)

### Viewing Lakekeeper Tables

Once connected, you can query:

```sql
-- See all namespaces
SELECT namespace_name FROM namespace;

-- See all tables
SELECT t.name, n.namespace_name 
FROM tabular t
JOIN namespace n ON t.namespace_id = n.namespace_id
WHERE t.typ = 'table';
```

