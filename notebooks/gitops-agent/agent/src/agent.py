# Firewall Automation Supervisor Agent
# To test locally, run `uv run agent.py` and then
# curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "Show me firewall logs for account A123"}'

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from git_agent import ado_git_agent


app = BedrockAgentCoreApp()


@tool
def query_account_details(account_identifier: str):
    """
    Query AWS account details from DynamoDB.

    Args:
        account_identifier: Account name, ID, or CIDR range to search for

    Returns:
        Account details including name, ID, CIDR ranges, and metadata
    """
    return {
        "account_name": "Production-App-Account",
        "account_id": "123456789012",
        "cidr_ranges": ["10.100.0.0/16", "10.101.0.0/16"],
        "environment": "production",
        "owner": "Platform Team",
        "region": "ap-southeast-2"
    }


@tool
def search_firewall_logs(
    query: str,
    time_range_hours: int = 1,
    account_filter: str = None,
    action_filter: str = None
):
    """
    Search AWS Network Firewall logs from OpenSearch Serverless.

    Args:
        query: Search query (IP, domain, protocol, etc.)
        time_range_hours: Time range to search (default: 1 hour)
        account_filter: Optional account ID filter
        action_filter: Optional action filter (ALLOW, DENY, DROP)

    Returns:
        Firewall log entries matching the query
    """
    return {
        "total_matches": 3,
        "logs": [
            {
                "timestamp": "2025-10-26T10:30:45Z",
                "account_id": "123456789012",
                "src_ip": "10.100.50.10",
                "dst_ip": "203.0.113.50",
                "protocol": "TCP",
                "dst_port": 443,
                "action": "ALLOW",
                "rule_id": "sid:1000001"
            },
            {
                "timestamp": "2025-10-26T10:28:12Z",
                "account_id": "123456789012",
                "src_ip": "10.100.50.10",
                "dst_ip": "198.51.100.20",
                "protocol": "TCP",
                "dst_port": 22,
                "action": "DENY",
                "rule_id": "sid:1000042"
            }
        ]
    }


# @tool
# def execute_git_operation(
#     operation: str,
#     rule_content: str = None,
#     branch_name: str = None,
#     commit_message: str = None
# ):
#     """
#     Execute Git operations for firewall rule management.

#     Args:
#         operation: Git operation to perform (clone, branch, commit, push, create_pr)
#         rule_content: Suricata rule content (for commits)
#         branch_name: Branch name for operations
#         commit_message: Commit message

#     Returns:
#         Result of the Git operation
#     """
#     return {
#         "operation": operation,
#         "status": "success",
#         "branch": branch_name or "firewall/add-tcp-production",
#         "commit_sha": "a1b2c3d4e5f6",
#         "message": f"Git operation '{operation}' completed successfully",
#         "pr_url": "https://dev.azure.com/org/project/_git/firewall-rules/pullrequest/42" if operation == "create_pr" else None
#     }


@tool
def query_servicenow(
    query_type: str,
    ci_name: str = None,
    account_id: str = None
):
    """
    Query ServiceNow CMDB for configuration items and create change requests.

    Args:
        query_type: Type of query (get_ci, verify_ci, create_change)
        ci_name: Configuration item name
        account_id: AWS account ID for lookup

    Returns:
        ServiceNow CMDB data or change request details
    """
    return {
        "ci_found": True,
        "ci_name": ci_name or "AWS-Production-Account",
        "ci_sys_id": "abc123def456",
        "operational_status": "Operational",
        "environment": "Production",
        "change_required": True,
        "change_number": "CHG0012345" if query_type == "create_change" else None
    }


@tool
def validate_ip_addresses(
    cidr_range: str = None,
    ip_address: str = None,
    check_conflicts: bool = True
):
    """
    Validate IP addresses and CIDR ranges using AWS VPC IPAM.

    Args:
        cidr_range: CIDR range to validate
        ip_address: Single IP address to validate
        check_conflicts: Check for conflicts with existing ranges

    Returns:
        Validation results and conflict information
    """
    return {
        "valid": True,
        "cidr": cidr_range or ip_address,
        "type": "private" if cidr_range and cidr_range.startswith("10.") else "public",
        "conflicts": [],
        "available": True,
        "message": "CIDR range is valid and available with no conflicts"
    }


model_id = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[
        query_account_details,
        search_firewall_logs,
        ado_git_agent,
        query_servicenow,
        validate_ip_addresses
    ],
    system_prompt="""You are the Firewall Automation Supervisor Agent. You coordinate multiple specialist agents to help users manage AWS Network Firewall rules.

Your specialist tools are:
1. query_account_details - Get AWS account information from DynamoDB
2. search_firewall_logs - Search firewall logs in OpenSearch Serverless
3. ado_git_agent - Manage firewall rules in Git (clone, branch, commit, push, PR creation)
4. query_servicenow - Query ServiceNow CMDB and create change requests
5. validate_ip_addresses - Validate IP addresses and CIDR ranges using AWS VPC IPAM

When a user asks to create or modify firewall rules, follow this workflow:
1. Understand the requirement (IPs, ports, protocol, action)
2. Query account details if account name is mentioned
3. Validate IP addresses/CIDR ranges
4. Search existing firewall logs to understand current traffic patterns
5. Query ServiceNow to verify the configuration item and create change request
6. Generate Suricata rule content
7. Execute Git operations (branch, commit, push, create PR)

Be conversational and explain what you're doing at each step.""",
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
