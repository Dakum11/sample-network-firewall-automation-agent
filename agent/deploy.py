import argparse
import os
import time

import boto3

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Deploy the AWS Network Firewall Automation Agent")
parser.add_argument("--region", required=True, help="AWS region (e.g., us-east-1)")
parser.add_argument("--account-id", required=True, help="AWS account ID")
parser.add_argument("--ecr-repository", required=True, help="URI of the ECR repository")
parser.add_argument("--version", required=True, help="Docker image version tag")
parser.add_argument("--agent-runtime-id", required=True, help="AgentCore runtime ID")
parser.add_argument("--subnets", required=True, help="Comma-separated list of subnet IDs")
parser.add_argument("--security-groups", required=True, help="Comma-separated list of security group IDs")
parser.add_argument("--role-name", required=True, help="IAM role name for agent execution")
args = parser.parse_args()

# Set variables from arguments
region = args.region
account_id = args.account_id
ecr_repository = args.ecr_repository
version_tag = args.version
agent_runtime_id = args.agent_runtime_id
subnets = [s.strip() for s in args.subnets.split(",")]
security_groups = [s.strip() for s in args.security_groups.split(",")]
role_name = args.role_name

# Load environment variables (no defaults - must be set)
azure_devops_org = os.environ["AZURE_DEVOPS_ORG"]
azure_devops_project = os.environ["AZURE_DEVOPS_PROJECT"]
repo_name = os.environ["REPO_NAME"]

# Configure the deployment
client = boto3.client("bedrock-agentcore-control", region_name=region)

response = client.update_agent_runtime(
    agentRuntimeId=agent_runtime_id,
    agentRuntimeArtifact={
        "containerConfiguration": {"containerUri": f"{ecr_repository}:{version_tag}"}
    },
    description="AWS Network Firewall Automation Agent",
    networkConfiguration={
        "networkMode": "VPC",
        "networkModeConfig": {
            "subnets": subnets,
            "securityGroups": security_groups,
        },
    },
    roleArn=f"arn:aws:iam::{account_id}:role/{role_name}",
    environmentVariables={
        "BYPASS_TOOL_CONSENT": "true",
        "AZURE_DEVOPS_ORG": azure_devops_org,
        "AZURE_DEVOPS_PROJECT": azure_devops_project,
        "REPO_NAME": repo_name,
        "EDITOR_DISABLE_BACKUP": "true",
    },
)

print("Agent Runtime created successfully!")
print(f"Agent Runtime ARN: {response['agentRuntimeArn']}")
print(f"Status: {response['status']}")
