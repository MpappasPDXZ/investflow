# Backend documentation

InvestFlow backend docs (Postgres tabular store + ADLS blobs).

| Doc | Purpose |
|-----|---------|
| [api-directory.md](./api-directory.md) | Every API route → screen → status |
| [data-model.md](./data-model.md) | Schema + relationships |
| [unit-test-catalog.md](./unit-test-catalog.md) | Planned/implemented unit tests |
| [exports/](./exports/) | Local snapshot dumps (gitignored PII); also uploaded to ADLS |

## Regenerate exports

```bash
cd backend
USE_POSTGRES_STORE=true uv run python -m app.scripts.export_postgres_to_adls
```

Writes parquet backups to ADLS and can leave local copies under `docs/exports/` (gitignored).
