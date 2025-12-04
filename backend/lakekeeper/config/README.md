# Lakekeeper Configuration Directory

This directory is mounted to `/etc/lakekeeper` in the Lakekeeper container (read-only).

## Configuration Methods

Lakekeeper can be configured via:

1. **Environment Variables** (Primary method - in `docker-compose.yml`)
   - `LAKEKEEPER__PG_DATABASE_URL_READ`
   - `LAKEKEEPER__PG_DATABASE_URL_WRITE`
   - `LAKEKEEPER__PG_ENCRYPTION_KEY`
   - `LAKEKEEPER__ENABLE_AZURE_SYSTEM_CREDENTIALS`
   - `LAKEKEEPER__BASE_URI`

2. **Configuration File** (`config.yaml`)
   - Lakekeeper will look for `/etc/lakekeeper/config.yaml`
   - Environment variables take precedence over config file values

## Files in This Directory

- `config.yaml` - Optional configuration file (if needed)
- `README.md` - This file

## Current Setup

Your Lakekeeper is configured via environment variables in `docker-compose.yml`. The configuration file is optional and primarily serves as documentation.

## Documentation

- [Lakekeeper Configuration Docs](https://docs.lakekeeper.io/docs/0.10.x/configuration/)
- [Lakekeeper GitHub](https://github.com/lakekeeper/lakekeeper)





