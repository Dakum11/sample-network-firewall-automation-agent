FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
WORKDIR /app

# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
    
# All environment variables in one layer
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    AWS_REGION=ap-southeast-2 \
    AWS_DEFAULT_REGION=ap-southeast-2



COPY . .
# Install from requirements file
RUN cd . && uv pip install .




RUN uv pip install aws-opentelemetry-distro>=0.10.1


# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

# Configure git for bedrock_agentcore user
RUN git config --global user.email "firewall-agent@example.com" && \
    git config --global user.name "firewall-automation-agent"

EXPOSE 9000
EXPOSE 8000
EXPOSE 8080

# Copy entire project (respecting .dockerignore)
COPY . .

# Use the full module path

CMD ["opentelemetry-instrument", "python", "-m", "agent"]
