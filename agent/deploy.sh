#!/bin/bash

set -e
# Script to deploy the agent application

# VARIABLES
AWS_REGION="ap-southeast-2"
AWS_ACCOUNT_ID="YOUR_ACCOUNT_ID"
REPOSITORY_NAME="firewall-automation/agent"

# DOCKER IMAGE BUILD AND PUSH
echo "Starting Docker image build and push to ECR..."

# Set ECR repository variable
ecr_repository="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPOSITORY_NAME"

# Create the ECR repository if it doesn't exist
aws ecr describe-repositories --repository-names $REPOSITORY_NAME --region $AWS_REGION >/dev/null 2>&1 ||
    aws ecr create-repository --repository-name $REPOSITORY_NAME --region $AWS_REGION

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "$ecr_repository"

# Get the version tag from pyproject.toml
version_line=$(grep -m1 '^version =' src/pyproject.toml)
version_tag=$(echo "$version_line" | cut -d'"' -f2)

# Build the Docker image
docker buildx build --platform linux/arm64 -t $ecr_repository:"$version_tag" -f src/Dockerfile --push ./src

echo "Docker image pushed to ECR: $ecr_repository:$version_tag"

# DEPLOY AGENT RUNTIME
uv run deploy.py --region $AWS_REGION --account-id $AWS_ACCOUNT_ID --ecr-repository "$ecr_repository" --version "$version_tag"
