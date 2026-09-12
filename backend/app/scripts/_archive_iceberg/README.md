# Archived Iceberg / Lakekeeper scripts

These one-off migration and Lakekeeper tooling scripts are retained for history only.
Production tabular store is Azure Postgres (`app` schema). Do not run against prod
expecting a live Lakekeeper catalog — `investflow-lakekeeper` was deleted 2026-09-12.

Active replacements:
- `../export_postgres_to_adls.py` — ADLS parquet backup of `app.*`
- `../smoke_postgres_writes.py` — create/read/update/delete smoke per write domain
