-- View Lakekeeper Database Schemas
-- Shows table name and all columns in each table

SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_name, ordinal_position;

