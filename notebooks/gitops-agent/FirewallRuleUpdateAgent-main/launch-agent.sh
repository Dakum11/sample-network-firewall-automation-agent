#!/bin/bash

# Source environment variables
source setup-env.sh

# Launch agent with environment variables
agentcore launch -a github_agent \
  -env REPO_URL="$REPO_URL" \
  -env PAT_TOKEN="$PAT_TOKEN" \
  -env GITHUB_API_URL="$GITHUB_API_URL" \
  -env VERBOSE="$VERBOSE"