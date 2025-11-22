# InvestFlow Backend

FastAPI backend application for InvestFlow rental property management system.

## Setup

1. Install UV (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Create virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. Set up environment variables (create `.env` file):
   ```
   DATABASE_URL=...
   AZURE_STORAGE_CONNECTION_STRING=...
   SECRET_KEY=...
   ```

4. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

## Development

- Run tests: `pytest`
- Format code: `ruff format .`
- Lint code: `ruff check .`
- Type check: `mypy app`

