"""
deploy.py — Create or update an Amazon Bedrock AgentCore runtime.

Usage:
    # First time: create a new runtime
    uv run deploy.py --create --region us-east-1 --account-id 123456789012 \
        --ecr-repository 123456789012.dkr.ecr.us-east-1.amazonaws.com/firewall-automation-agent \
        --version 1.0.0 --subnets subnet-aaa,subnet-bbb --security-groups sg-xxx \
        --role-name FirewallAutomation-AgentCore-Execution-Role

    # Subsequent deploys: update an existing runtime
    uv run deploy.py --agent-runtime-id <RUNTIME_ID> --region us-east-1 --account-id 123456789012 \
        --ecr-repository 123456789012.dkr.ecr.us-east-1.amazonaws.com/firewall-automation-agent \
        --version 1.0.1 --subnets subnet-aaa,subnet-bbb --security-groups sg-xxx \
        --role-name FirewallAutomation-AgentCore-Execution-Role
"""

import argparse
import os
import sys
import time

import boto3


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create or update an Amazon Bedrock AgentCore runtime for the Network Firewall Automation Agent."
    )
    parser.add_argument("--region", required=True, help="AWS region (e.g., us-east-1)")
    parser.add_argument("--account-id", required=True, help="AWS account ID")
    parser.add_argument("--ecr-repository", required=True, help="Full ECR repository URI (without tag)")
    parser.add_argument("--version", required=True, help="Docker image version tag")
    parser.add_argument("--subnets", required=True, help="Comma-separated list of subnet IDs for VPC configuration")
    parser.add_argument("--security-groups", required=True, help="Comma-separated list of security group IDs")
    parser.add_argument("--role-name", required=True, help="IAM execution role name for the agent")

    # Mode: create vs update
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--create", action="store_true", help="Create a new AgentCore runtime (first-time setup)")
    mode_group.add_argument("--agent-runtime-id", help="Existing AgentCore runtime ID to update")

    # Optional
    parser.add_argument("--runtime-name", default="firewall-automation-agent",
                        help="Name for the new runtime (only used with --create, default: firewall-automation-agent)")

    return parser.parse_args()


def get_environment_variables():
    """Collect environment variables to pass to the AgentCore runtime."""
    env_vars = {
        "BYPASS_TOOL_CONSENT": "true",
        "EDITOR_DISABLE_BACKUP": "true",
    }

    # Optional env vars — pass through if set
    optional_vars = [
        "AZURE_DEVOPS_ORG",
        "AZURE_DEVOPS_PROJECT",
        "REPO_NAME",
        "AZURE_DEVOPS_SECRET_NAME",
        "CROSS_ACCOUNT_ROLE_ARN",
        "DYNAMODB_ACCOUNT_METADATA_TABLE_NAME",
        "IPAM_SECRET_NAME",
        "AGENTCORE_MEMORY_ID",
        "BEDROCK_MODEL_ID",
    ]

    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            env_vars[var] = value

    return env_vars


def create_runtime(client, args):
    """Create a new AgentCore runtime."""
    subnets = [s.strip() for s in args.subnets.split(",")]
    security_groups = [s.strip() for s in args.security_groups.split(",")]
    role_arn = f"arn:aws:iam::{args.account_id}:role/{args.role_name}"

    print(f"Creating new AgentCore runtime: {args.runtime_name}")
    print(f"  Container: {args.ecr_repository}:{args.version}")
    print(f"  Role: {role_arn}")
    print(f"  Subnets: {subnets}")
    print(f"  Security Groups: {security_groups}")

    response = client.create_agent_runtime(
        agentRuntimeName=args.runtime_name,
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": f"{args.ecr_repository}:{args.version}"
            }
        },
        description="AWS Network Firewall Automation Agent — multi-agent system for automated firewall rule management",
        networkConfiguration={
            "networkMode": "VPC",
            "networkModeConfig": {
                "subnets": subnets,
                "securityGroups": security_groups,
            },
        },
        roleArn=role_arn,
        environmentVariables=get_environment_variables(),
    )

    runtime_id = response["agentRuntimeId"]
    print(f"\nAgent Runtime created!")
    print(f"  Runtime ID: {runtime_id}")
    print(f"  ARN: {response['agentRuntimeArn']}")
    print(f"  Status: {response['status']}")
    print(f"\n{'='*60}")
    print(f"  IMPORTANT: Save your runtime ID in .env:")
    print(f"  AGENT_RUNTIME_ID={runtime_id}")
    print(f"{'='*60}")

    # Wait for runtime to become READY
    wait_for_ready(client, runtime_id)

    return runtime_id


def update_runtime(client, args):
    """Update an existing AgentCore runtime with new container image."""
    subnets = [s.strip() for s in args.subnets.split(",")]
    security_groups = [s.strip() for s in args.security_groups.split(",")]
    role_arn = f"arn:aws:iam::{args.account_id}:role/{args.role_name}"

    print(f"Updating AgentCore runtime: {args.agent_runtime_id}")
    print(f"  Container: {args.ecr_repository}:{args.version}")
    print(f"  Role: {role_arn}")
    print(f"  Subnets: {subnets}")
    print(f"  Security Groups: {security_groups}")

    response = client.update_agent_runtime(
        agentRuntimeId=args.agent_runtime_id,
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": f"{args.ecr_repository}:{args.version}"
            }
        },
        description="AWS Network Firewall Automation Agent — multi-agent system for automated firewall rule management",
        networkConfiguration={
            "networkMode": "VPC",
            "networkModeConfig": {
                "subnets": subnets,
                "securityGroups": security_groups,
            },
        },
        roleArn=role_arn,
        environmentVariables=get_environment_variables(),
    )

    print(f"\nAgent Runtime updated!")
    print(f"  ARN: {response['agentRuntimeArn']}")
    print(f"  Status: {response['status']}")

    # Wait for runtime to become READY
    wait_for_ready(client, args.agent_runtime_id)

    return args.agent_runtime_id


def wait_for_ready(client, runtime_id, timeout=300, interval=10):
    """Poll the runtime status until it reaches READY or times out."""
    print(f"\nWaiting for runtime to become READY (timeout: {timeout}s)...")
    elapsed = 0
    while elapsed < timeout:
        response = client.get_agent_runtime(agentRuntimeId=runtime_id)
        status = response["status"]
        if status == "READY":
            print(f"  Runtime is READY! (took {elapsed}s)")
            return
        elif status in ("FAILED", "DELETED"):
            print(f"  ERROR: Runtime entered {status} state.")
            if "failureReason" in response:
                print(f"  Reason: {response['failureReason']}")
            sys.exit(1)
        else:
            print(f"  Status: {status} ({elapsed}s elapsed)")
            time.sleep(interval)
            elapsed += interval

    print(f"  WARNING: Timed out after {timeout}s. Current status: {status}")
    print(f"  Check manually: aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id {runtime_id} --region {args.region}")


def main():
    args = parse_args()

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)

    if args.create:
        create_runtime(client, args)
    else:
        update_runtime(client, args)


if __name__ == "__main__":
    main()
