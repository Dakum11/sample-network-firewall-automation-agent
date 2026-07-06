#!/bin/bash

# IPAM Agent Environment Setup
# Run this script to set up environment variables for the ipam agent
# source setup-env.sh

export SOLIDSERVER_URL="https://your-ipam-server.example.com"
export USERNAME="mlops-test"
export PASSWORD="xxxx"
export VERBOSE="false"

echo "Environment variables set:"
echo "IPAM_URL=$SOLIDSERVER_URL"
echo "USERNAME=$USERNAME"
echo "VERBOSE=$VERBOSE"
