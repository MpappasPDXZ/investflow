# Archived Iceberg / Lakekeeper / one-off scripts

Retained for history only. Production tabular store is Azure Postgres (`app` schema).
Do not run against prod expecting a live Lakekeeper catalog — `investflow-lakekeeper`
was deleted 2026-09-12.

Also includes former `app/scripts/` one-offs (lease mapping, backups, checks) that are
no longer part of the active allowlist.

Active scripts (parent directory):
- `../export_postgres_to_adls.py` — ADLS parquet backup of `app.*`
- `../smoke_postgres_writes.py` — create/read/update/delete smoke per write domain
