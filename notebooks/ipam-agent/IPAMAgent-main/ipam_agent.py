# Firewall Automation Supervisor Agent
# To test locally, run `uv run agent.py` and then
# curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "Show me firewall logs for account A123"}'
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from utils.ipam_utils import check_cidr_range, check_ip_addresses, classify_ip_or_cidr
import logging
logging.basicConfig(level=logging.DEBUG)
app = BedrockAgentCoreApp()

@tool
def validate_ip_addresses(
    ip_address: str = None,
    cidr_range: str = None,
):
    """
    Validate IP addresses and CIDR ranges using AWS VPC IPAM.

    Args:
        ip_address: Single IP address to validate
        cidr_range: CIDR range to validate

    Returns:
        Validation results and conflict information
    """
    if cidr_range:
        validation_result = check_cidr_range(cidr_range)
        if validation_result.get("status") == "error":
            valid = False
            message = f"Error validating CIDR range: {validation_result.get('error')}"
        if validation_result.get("exists"):
            valid = False
            message = f"CIDR range conflict: {validation_result.get('message')}"
        else:
            valid = True
            message = f"CIDR range {cidr_range} is valid and available with no conflicts"
    elif ip_address:
        validation_result = check_ip_addresses(ip_address)
        if validation_result.get("status") == "error":
            valid = False
            message = f"Error validating IP address: {validation_result.get('error')}"
        if validation_result.get("exists"):
            valid = False
            message = f"IP address conflict: {validation_result.get('message')}"
        else:
            valid = True
            message = f"IP address {ip_address} is valid and available with no conflicts"
    return {
        "valid": valid,
        "cidr": cidr_range or ip_address,
        "type": classify_ip_or_cidr(cidr_range or ip_address),
        "available": valid,
        "message": message
    }


model_id = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[
        validate_ip_addresses
    ],
    system_prompt="""You are a IPAM agent. Your task is to:
1. Validate if given IP addresses or CIDR ranges are available in the IP Address Management (IPAM) system.
2. Identify any conflicts with existing allocations in the IPAM.
Use the provided tool to accomplish these tasks."""
)


@app.entrypoint
async def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    agent_stream = agent.stream_async(user_input)
    tool_name = None
    try:
        async for event in agent_stream:
            if (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                yield f"\n\n🔧 Using tool: {tool_name}\n\n"

            if "data" in event:
                tool_name = None
                yield event["data"]
    except Exception as e:
        yield f"Error: {str(e)}"


if __name__ == "__main__":
    app.run()
