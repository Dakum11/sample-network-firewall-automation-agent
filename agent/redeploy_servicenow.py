#!/usr/bin/env python3
"""One-off redeploy: fix VPC mismatch + inject ServiceNow secret region env vars."""
import sys
import time
import boto3

REGION = "us-east-1"
ACCOUNT = "868287237678"
RUNTIME_ID = "firewall_automation_agent-rDUSNID5PX"
ECR = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/firewall-automation-agent:latest"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/FirewallAutomation-AgentCore-Execution-Role"
SUBNETS = ["subnet-0b4ea42f90ebf812f"]          # us-east-1a (use1-az4, SUPPORTED), private + NAT egress, vpc-0757a364e9d6b3876
SECURITY_GROUPS = ["sg-0817640507dc583fb"]      # default SG in the SAME vpc, all outbound allowed

ENV_VARS = {
    "BYPASS_TOOL_CONSENT": "true",
    "EDITOR_DISABLE_BACKUP": "true",
    "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # Ensure the secretsmanager client hits the region where the secret lives,
    # overriding the Dockerfile's hardcoded AWS_REGION=ap-southeast-2.
    "AWS_REGION": REGION,
    "AWS_DEFAULT_REGION": REGION,
    "SERVICENOW_SECRET_REGION": REGION,
    "SERVICENOW_SECRET_NAME": "firewall-automation/servicenow/credentials",
}

c = boto3.client("bedrock-agentcore-control", region_name=REGION)

print(f"Updating runtime {RUNTIME_ID}")
print(f"  image  : {ECR}")
print(f"  subnets: {SUBNETS}")
print(f"  sgs    : {SECURITY_GROUPS}")
resp = c.update_agent_runtime(
    agentRuntimeId=RUNTIME_ID,
    agentRuntimeArtifact={"containerConfiguration": {"containerUri": ECR}},
    description="AWS Network Firewall Automation Agent — ServiceNow demo (Secrets Manager creds, fixed VPC)",
    networkConfiguration={
        "networkMode": "VPC",
        "networkModeConfig": {"subnets": SUBNETS, "securityGroups": SECURITY_GROUPS},
    },
    roleArn=ROLE_ARN,
    environmentVariables=ENV_VARS,
)
print("  submitted, status:", resp["status"])

# Poll for READY
timeout, interval, elapsed = 420, 15, 0
while elapsed < timeout:
    r = c.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
    st = r["status"]
    if st == "READY":
        print(f"\nRuntime READY (after {elapsed}s). version={r.get('agentRuntimeVersion')}")
        sys.exit(0)
    if st in ("UPDATE_FAILED", "FAILED", "DELETED"):
        print(f"\nFAILED: status={st} reason={r.get('failureReason')}")
        sys.exit(1)
    print(f"  status={st} ({elapsed}s)")
    time.sleep(interval)
    elapsed += interval
print(f"\nTIMEOUT after {timeout}s; last status={st}")
sys.exit(2)
