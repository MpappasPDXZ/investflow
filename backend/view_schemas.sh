#!/bin/bash
# Script to view Lakekeeper database schemas
# Usage: ./view_schemas.sh

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep POSTGRES | xargs)
fi

echo "Connecting to PostgreSQL database..."
echo "Host: ${POSTGRES_HOST:-if-postgres.postgres.database.azure.com}"
echo "Database: ${POSTGRES_DB:-investflow}"
echo "User: ${POSTGRES_USER:-pgadmin}"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "psql not found. Please install PostgreSQL client tools."
    echo "Or use DBeaver with the connection details from lakekeeper/DBEAVER_CONNECTION.md"
    exit 1
fi

# Run the schema queries
psql "postgresql://${POSTGRES_USER:-pgadmin}:${POSTGRES_PASSWORD}@${POSTGRES_HOST:-if-postgres.postgres.database.azure.com}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-investflow}?sslmode=require" -f view_lakekeeper_schemas.sql

