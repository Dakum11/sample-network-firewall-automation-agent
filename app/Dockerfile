FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Sync dependencies using uv (creates .venv and installs from lock file)
RUN uv sync --frozen --no-dev

# Copy static assets
COPY static/ ./static/

# Copy application code
COPY app.py .

# Expose the application port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/health || exit 1

# Run with gunicorn for production (multi-worker, production-grade)
CMD ["uv", "run", "gunicorn", "app:app", "--bind", "0.0.0.0:8501", "--workers", "4", "--timeout", "900", "--worker-class", "gthread", "--threads", "2"]
