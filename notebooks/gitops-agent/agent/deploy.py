import time

import boto3
from bedrock_agentcore_starter_toolkit import Runtime

# Initialize the runtime toolkit
region = "ap-southeast-2"

agentcore_runtime = Runtime()

# Configure the deployment
response = agentcore_runtime.configure(
    entrypoint="src/agent.py",
    execution_role="arn:aws:iam::YOUR_ACCOUNT_ID:role/FW-Automation-AgentCore-Execution-Role",
    code_build_execution_role="arn:aws:iam::YOUR_ACCOUNT_ID:role/AmazonBedrockAgentCoreSDKCodeBuild-ap-southeast-2-5432796e49",
    ecr_repository="YOUR_ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/firewall-automation/agent",
    requirements_file="src/requirements.txt",
    region=region,
    agent_name="firewall_automation_agent",
    memory_mode="STM_ONLY",
)

print("Configuration completed:", response)

launch_result = agentcore_runtime.launch()
print("Launch completed:", launch_result.agent_arn)

# Wait for the agent to be ready
status_response = agentcore_runtime.status()
status = status_response.endpoint["status"]

end_status = ["READY", "CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"]
while status not in end_status:
    print(f"Waiting for deployment... Current status: {status}")
    time.sleep(10)
    status_response = agentcore_runtime.status()
    status = status_response.endpoint["status"]

if status == "READY":
    runtime_id = status_response.agent["agentRuntimeId"]

    # Update the runtime to be deployed in VPC
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    response = client.update_agent_runtime(
        agentRuntimeId=runtime_id,
        networkConfiguration={
            "networkMode": "VPC",
            "networkModeConfig": {
                "subnets": ["subnet-0346050dd733b71b9", "subnet-0ee37898a908e35b6"],
                "securityGroups": ["sg-0302b0e114f205955"],
            },
        },
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": "YOUR_ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/firewall-automation/agent:latest"
            }
        },
        roleArn="arn:aws:iam::YOUR_ACCOUNT_ID:role/FW-Automation-AgentCore-Execution-Role",
    )
