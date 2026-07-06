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
RUN --mount=type=secret,id=uv.toml,dst=/root/.config/uv/uv.toml uv sync --frozen --no-dev

# Copy static assets
COPY static/ ./static/

# Copy application code
COPY app.py .

# Expose the port Streamlit will run on
EXPOSE 8501

# Set Streamlit configuration
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run the Streamlit app using uv run (automatically uses the .venv)
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

