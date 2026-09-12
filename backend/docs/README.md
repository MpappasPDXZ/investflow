# Backend documentation

InvestFlow backend docs for the Lakekeeper → Postgres migration.

| Doc | Purpose |
|-----|---------|
| [api-directory.md](./api-directory.md) | Every API route → screen → status |
| [data-model.md](./data-model.md) | Generated Iceberg/Postgres schema + relationships |
| [unit-test-catalog.md](./unit-test-catalog.md) | Planned/implemented unit tests |
| [exports/](./exports/) | Local snapshot dumps (gitignored PII); also uploaded to ADLS |

## Regenerate exports

```bash
cd backend
uv run python -m app.scripts.export_iceberg_docs
```

Uploads parquet + markdown for every `investflow.*` table to ADLS under `backups/docs/{timestamp}/` and writes local copies under `docs/exports/{timestamp}/`.
