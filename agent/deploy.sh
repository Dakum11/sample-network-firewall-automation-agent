#!/bin/bash

set -e

# =============================================================================
# deploy.sh — Build, push, and deploy the Network Firewall Automation Agent
# =============================================================================
# Usage:
#   ./deploy.sh              # Update an existing AgentCore runtime
#   ./deploy.sh --create     # Create a new AgentCore runtime (first time)
#
# Configuration is loaded from ../.env (project root). Copy .env.example to .env
# and fill in your values before running.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# -----------------------------------------------------------------------------
# Load .env file from project root
# -----------------------------------------------------------------------------
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading configuration from $ENV_FILE"
    # Export variables from .env (skip comments and blank lines)
    set -a
    # shellcheck disable=SC1090
    source <(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$')
    set +a
else
    echo "WARNING: No .env file found at $ENV_FILE"
    echo "Copy .env.example to .env and configure your values."
    echo "Falling back to environment variables..."
fi

# -----------------------------------------------------------------------------
# Validate required variables
# -----------------------------------------------------------------------------
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
ECR_REPOSITORY_NAME="${ECR_REPOSITORY_NAME:-firewall-automation-agent}"
AGENT_RUNTIME_ID="${AGENT_RUNTIME_ID:-}"
AGENT_SUBNETS="${AGENT_SUBNETS:-}"
AGENT_SECURITY_GROUPS="${AGENT_SECURITY_GROUPS:-}"
AGENT_EXECUTION_ROLE_NAME="${AGENT_EXECUTION_ROLE_NAME:-FirewallAutomation-AgentCore-Execution-Role}"

# Get account ID from AWS if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "AWS_ACCOUNT_ID not set, detecting from AWS CLI..."
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo "Detected account ID: $AWS_ACCOUNT_ID"
fi

# Check for create mode
CREATE_MODE=false
if [[ "$1" == "--create" ]]; then
    CREATE_MODE=true
fi

# Validate required variables
if [ "$CREATE_MODE" = false ] && [ -z "$AGENT_RUNTIME_ID" ]; then
    echo "ERROR: AGENT_RUNTIME_ID is required for updating a runtime."
    echo "Set it in .env or run with --create to create a new runtime."
    exit 1
fi

if [ -z "$AGENT_SUBNETS" ]; then
    echo "ERROR: AGENT_SUBNETS is required. Set it in .env (comma-separated subnet IDs)."
    exit 1
fi

if [ -z "$AGENT_SECURITY_GROUPS" ]; then
    echo "ERROR: AGENT_SECURITY_GROUPS is required. Set it in .env (comma-separated SG IDs)."
    exit 1
fi

# =============================================================================
# DOCKER IMAGE BUILD AND PUSH
# =============================================================================
echo ""
echo "=========================================="
echo " Building and pushing Docker image to ECR"
echo "=========================================="

# Set ECR repository URI
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME"

# Create the ECR repository if it doesn't exist
aws ecr describe-repositories --repository-names "$ECR_REPOSITORY_NAME" --region "$AWS_REGION" >/dev/null 2>&1 || \
    aws ecr create-repository --repository-name "$ECR_REPOSITORY_NAME" --region "$AWS_REGION"

# Authenticate Docker to ECR
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Get the version tag from src/pyproject.toml
VERSION_LINE=$(grep -m1 '^version =' src/pyproject.toml)
VERSION_TAG=$(echo "$VERSION_LINE" | cut -d'"' -f2)

echo "Building image: $ECR_URI:$VERSION_TAG"

# Build and push the Docker image
docker buildx build --platform linux/arm64 -t "$ECR_URI:$VERSION_TAG" -f src/Dockerfile --push ./src

echo "Docker image pushed: $ECR_URI:$VERSION_TAG"

# =============================================================================
# DEPLOY AGENT RUNTIME
# =============================================================================
echo ""
echo "=========================================="
echo " Deploying AgentCore runtime"
echo "=========================================="

# Build the deploy.py command
DEPLOY_ARGS=(
    --region "$AWS_REGION"
    --account-id "$AWS_ACCOUNT_ID"
    --ecr-repository "$ECR_URI"
    --version "$VERSION_TAG"
    --subnets "$AGENT_SUBNETS"
    --security-groups "$AGENT_SECURITY_GROUPS"
    --role-name "$AGENT_EXECUTION_ROLE_NAME"
)

if [ "$CREATE_MODE" = true ]; then
    DEPLOY_ARGS+=(--create)
    echo "Mode: CREATE (new runtime)"
else
    DEPLOY_ARGS+=(--agent-runtime-id "$AGENT_RUNTIME_ID")
    echo "Mode: UPDATE (runtime: $AGENT_RUNTIME_ID)"
fi

uv run deploy.py "${DEPLOY_ARGS[@]}"

echo ""
echo "=========================================="
echo " Deployment complete!"
echo "=========================================="
