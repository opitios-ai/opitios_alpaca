FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# curl is needed for the HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (secrets.yml is excluded via .dockerignore and must be
# bind-mounted at runtime: -v /path/to/secrets.yml:/app/secrets.yml:ro)
COPY . .

# Non-root user; make sure runtime dirs exist and are writable
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/static /app/logs \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8090/health || exit 1

# Run uvicorn directly (never `python main.py`, which enables --reload when
# settings.debug is true). Single worker: the auto-sell loop must not run twice.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
