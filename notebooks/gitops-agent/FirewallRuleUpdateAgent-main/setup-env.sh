#!/bin/bash

# GitHub Agent Environment Setup
# Run this script to set up environment variables for the GitHub agent
# source setup-env.sh

export REPO_URL="https://github.com/<your-org>/<your-firewall-rules-repo>.git"
export PAT_TOKEN="<your-github-personal-access-token>"
export GITHUB_API_URL="https://api.github.com/repos/<your-org>/<your-firewall-rules-repo>/pulls"
export VERBOSE="false"

echo "Environment variables set:"
echo "REPO_URL=$REPO_URL"
echo "PAT_TOKEN=${PAT_TOKEN:0:20}..."
echo "GITHUB_API_URL=$GITHUB_API_URL"
echo "VERBOSE=$VERBOSE"
