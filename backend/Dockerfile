# Backend Dockerfile - InvestFlow
FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for compiling Cython extensions + LaTeX for lease generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    wget \
    perl \
    curl \
    && wget -qO- "https://yihui.org/tinytex/install-bin-unix.sh" | sh \
    && /root/bin/tlmgr install enumitem titlesec fancyhdr tabularx \
    && rm -rf /var/lib/apt/lists/*

# Add TinyTeX to PATH
ENV PATH="/root/bin:$PATH"

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Configure SSL certificates for DuckDB Azure connections
# The python:slim image already has ca-certificates installed
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_DIR=/etc/ssl/certs

# Copy dependency files
COPY pyproject.toml ./

# Install Cython first so PyIceberg can build with optimized Avro decoder
RUN uv pip install --system cython

# Install all dependencies (force source build for pyiceberg to get Cython extensions)
RUN uv pip install --system --no-binary pyiceberg -e .

# Copy application code
COPY app/ ./app/

# Copy migration scripts
#COPY migrate_user_cache.py ./
#COPY migrate_financial_performance.py ./
#COPY migrate_populate_financial_performance_cache.py ./

# Expose port
EXPOSE 8000

# Unset PORT env var that Azure might inject, then run on port 8000
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]

