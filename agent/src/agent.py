# Firewall Automation Supervisor Agent

import logging
import os
from datetime import datetime

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import editor, file_read, file_write

from subagent.firewall_logs_agent import firewall_logs_agent
from subagent.gitops_tools import (
    clone_repo,
    commit_and_push,
    create_pull_request,
    format_pr_description,
)
from utils.account_details_utils import (
    DYNAMODB_ACCOUNT_METADATA_TABLE_NAME,
    DYNAMODB_DEPLOYMENT_STATE_TABLE_SUFFIX,
    CROSS_ACCOUNT_ROLE_ARN,
    AccountDetailsClient,
)
from utils.ipam_utils import check_cidr_range, check_ip_addresses, classify_ip_or_cidr
import socket


app = BedrockAgentCoreApp()
memory_client = MemoryClient(region_name=os.getenv('AWS_REGION', 'us-east-1'))

logger = logging.getLogger(__name__)

# Global agent instance - will be initialized with first request
agent = None


@tool
def query_account_details(account_identifier: str, region: str):
    """
    Query AWS account details from DynamoDB.

    This tool can search by:
    - Account ID (12-digit number)
    - Account Name (exact or partial match)
    - VPC name (exact or partial match)
    - CIDR range (exact or partial match)

    Args:
        account_identifier: Account ID, Account Name, VPC name, or CIDR range to search for
        region: AWS region to search for account metadata (e.g., us-east-1, ap-southeast-2, ca-central-1).

    Returns:
        Account details including VPC information and metadata
    """
    _account_client = AccountDetailsClient(
        region,
        DYNAMODB_DEPLOYMENT_STATE_TABLE_SUFFIX,
        DYNAMODB_ACCOUNT_METADATA_TABLE_NAME,
        CROSS_ACCOUNT_ROLE_ARN,
    )
    try:
        print(f"Querying account details for: {account_identifier}")

        # Direct account ID lookup
        if account_identifier.isdigit() and len(account_identifier) == 12:
            account = _account_client.get_account_by_id(account_identifier)
            if account:
                vpc_info = account.get("vpc_info", {})
                return {
                    "found": True,
                    "match_type": "exact_id",
                    "account_id": account.get("account-no"),
                    "vpc_id": vpc_info.get("vpc_id"),
                    "vpc_name": vpc_info.get("vpc_name"),
                    "main_cidr": vpc_info.get("main_cidr"),
                    "subnets_count": vpc_info.get("subnets_count"),
                    "subnets": vpc_info.get("subnets", []),
                    "endpoints_count": vpc_info.get("endpoints"),
                }
        else:
            # Search-based lookup
            matches = _account_client.search_accounts(account_identifier)
            if matches:
                best_match = matches[0]
                account = best_match["account"]
                vpc_info = account.get("vpc_info", {})

                return {
                    "found": True,
                    "match_type": best_match["match_type"],
                    "confidence_score": best_match["score"],
                    "account_id": account.get("account-no"),
                    "vpc_id": vpc_info.get("vpc_id"),
                    "vpc_name": vpc_info.get("vpc_name"),
                    "main_cidr": vpc_info.get("main_cidr"),
                    "subnets_count": vpc_info.get("subnets_count"),
                    "subnets": vpc_info.get("subnets", []),
                    "endpoints_count": vpc_info.get("endpoints"),
                    "alternatives": [
                        {
                            "account_id": m["account"].get("account-no"),
                            "vpc_name": m["account"]
                            .get("vpc_info", {})
                            .get("vpc_name"),
                            "main_cidr": m["account"]
                            .get("vpc_info", {})
                            .get("main_cidr"),
                            "match_type": m["match_type"],
                            "score": m["score"],
                        }
                        for m in matches[1:5]  # Show top 4 alternatives
                    ],
                }

        return {
            "found": False,
            "searched_for": account_identifier,
            "message": f"No account found matching '{account_identifier}'",
        }

    except Exception as e:
        print(f"Error in query_account_details: {str(e)}")
        return {"error": str(e), "found": False, "searched_for": account_identifier}

@tool
def nslookup(hostname: str = None, ip_address: str = None):
    """
    Perform DNS lookup to resolve hostnames to IP addresses or reverse lookup IPs to hostnames.
    
    Use this tool to:
    - Resolve domain names to IP addresses (forward lookup)
    - Resolve IP addresses to hostnames (reverse lookup)
    - Verify DNS configuration for firewall rules
    
    Args:
        hostname: Domain name to resolve (e.g., 'example.com', 'api.service.internal')
        ip_address: IP address for reverse lookup (e.g., '8.8.8.8')
        
    Returns:
        Dict with DNS resolution results including IP addresses or hostnames
    """
    if not hostname and not ip_address:
        return {"success": False, "error": "Must provide either hostname or ip_address"}
    
    try:
        if hostname:
            ip_addresses = socket.getaddrinfo(hostname, None)
            unique_ips = list(set([addr[4][0] for addr in ip_addresses]))
            return {
                "success": True,
                "query": hostname,
                "query_type": "forward",
                "ip_addresses": unique_ips,
                "message": f"✅ {hostname} resolves to: {', '.join(unique_ips)}"
            }
        else:
            hostname_result = socket.gethostbyaddr(ip_address)
            return {
                "success": True,
                "query": ip_address,
                "query_type": "reverse",
                "hostname": hostname_result[0],
                "aliases": hostname_result[1],
                "message": f"✅ {ip_address} resolves to: {hostname_result[0]}"
            }
    except socket.gaierror as e:
        return {
            "success": False,
            "query": hostname or ip_address,
            "query_type": "forward" if hostname else "reverse",
            "error": str(e),
            "message": f"❌ DNS lookup failed: {str(e)}"
        }



@tool
def validate_ip_addresses(ip_address: str = None, cidr_range: str = None):
    """
    CRITICAL: Validate IP addresses and CIDR ranges against corporate IPAM database.
    
    This tool checks if IPs/CIDRs are registered in the corporate IPAM system.
    ALWAYS use this tool before creating firewall rules to ensure proper IP allocation.
    
    IMPORTANT - Understanding Results:
    - exists=True: IP/CIDR is registered in IPAM (GOOD - can proceed)
    - exists=False: IP/CIDR is NOT in IPAM (WARNING - may indicate):
      * Unallocated IP space
      * Typo in the IP/CIDR provided
      * IP not yet registered in IPAM
      * Potential security risk
    
    When exists=False, you MUST:
    1. Alert the user that the IP/CIDR is missing from IPAM
    2. Ask if they want to proceed anyway
    3. Document this as a risk in the PR description
    
    Args:
        ip_address: Single IP address to validate (e.g., '10.9.56.24')
        cidr_range: CIDR range to validate (e.g., '10.9.56.0/24')
        
    Returns:
        Dict with:
        - valid: Whether IP/CIDR exists in IPAM
        - exists: Same as valid (for clarity)
        - message: Detailed explanation including owner and region if found
        - type: Classification (private/public/CIDR/IP)
        - cidr: The IP/CIDR that was checked
    """
    if not ip_address and not cidr_range:
        return {
            "valid": False,
            "exists": False,
            "message": "Error: Must provide either ip_address or cidr_range",
            "type": "error"
        }
    
    if cidr_range:
        validation_result = check_cidr_range(cidr_range)
        if validation_result.get("status") == "error":
            return {
                "valid": False,
                "exists": False,
                "cidr": cidr_range,
                "type": classify_ip_or_cidr(cidr_range),
                "message": f"❌ Error validating CIDR range: {validation_result.get('error')}"
            }
        if validation_result.get("exists"):
            return {
                "valid": True,
                "exists": True,
                "cidr": cidr_range,
                "type": classify_ip_or_cidr(cidr_range),
                "message": f"✅ {validation_result.get('message')}"
            }
        else:
            return {
                "valid": False,
                "exists": False,
                "cidr": cidr_range,
                "type": classify_ip_or_cidr(cidr_range),
                "message": f"⚠️ WARNING: CIDR range {cidr_range} does NOT exist in IPAM. This may indicate unallocated IP space or a registration issue."
            }
    
    elif ip_address:
        validation_result = check_ip_addresses(ip_address)
        if validation_result.get("status") == "error":
            return {
                "valid": False,
                "exists": False,
                "cidr": ip_address,
                "type": classify_ip_or_cidr(ip_address),
                "message": f"❌ Error validating IP address: {validation_result.get('error')}"
            }
        if validation_result.get("exists"):
            return {
                "valid": True,
                "exists": True,
                "cidr": ip_address,
                "type": classify_ip_or_cidr(ip_address),
                "message": f"✅ {validation_result.get('message')}"
            }
        else:
            return {
                "valid": False,
                "exists": False,
                "cidr": ip_address,
                "type": classify_ip_or_cidr(ip_address),
                "message": f"⚠️ WARNING: IP address {ip_address} does NOT exist in IPAM. This may indicate unallocated IP space or a registration issue."
            }



def initialize_agent(actor_id, session_id):
    """Initialize the agent for first use"""
    global agent

    logger.info(f"Initializing agent for actor_id={actor_id}, session_id={session_id}")

    model_id = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-sonnet-4-20250514-v1:0')
    memory_id = os.getenv('AGENTCORE_MEMORY_ID')

    # Create model and memory hook
    logger.info(f"Creating model with ID: {model_id}")
    model = BedrockModel(model_id=model_id)

    # Configure memory (optional — agent works without it)
    session_manager = None
    if memory_id:
        try:
            agentcore_memory_config = AgentCoreMemoryConfig(
                memory_id=memory_id,
                session_id=f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                actor_id=f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            )
            session_manager = AgentCoreMemorySessionManager(
                agentcore_memory_config=agentcore_memory_config, region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
            logger.info("AgentCore Memory configured successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize AgentCore Memory: {e}. Agent will run without memory.")
    else:
        logger.info("AGENTCORE_MEMORY_ID not set — running without conversation memory")

    # Create agent with proper initial state
    logger.info("Creating agent with memory hook")
    agent = Agent(
        model=model,
        session_manager=session_manager,
        tools=[
            query_account_details,
            firewall_logs_agent,
            clone_repo,
            commit_and_push,
            format_pr_description,
            create_pull_request,
            validate_ip_addresses,
            nslookup,
            editor,
            file_read,
            file_write,
        ],
        system_prompt="""You are the Firewall Automation Agent. You help users manage AWS Network Firewall rules.

Your tools:
1. query_account_details - Get AWS account information
2. firewall_logs_agent - Search and analyze firewall logs
3. validate_ip_addresses - Validate IPs and CIDR ranges against IPAM
4. clone_repo - Clone repository and create branch
5. commit_and_push - Commit and push changes
6. format_pr_description - Format PR description with all required fields
7. create_pull_request - Create pull request
8. editor, file_read, file_write - File operations

CRITICAL WORKFLOW for creating/modifying firewall rules:
1. Understand requirements - Extract all IPs, CIDRs, ports, protocols
2. Query account details - Verify AWS account and VPC information
3. **VALIDATE ALL IPs/CIDRs WITH IPAM** - This is MANDATORY
   - Check EVERY source and destination IP/CIDR
   - If ANY IP/CIDR is missing from IPAM (exists=False):
     * STOP and alert the user immediately
     * Explain: "⚠️ WARNING: {IP/CIDR} is NOT registered in IPAM"
     * Ask: "This IP/CIDR is not in the corporate IPAM database. Do you want to proceed anyway?"
     * If user confirms, document this risk in PR description
4. Search firewall logs - Check past 7 days for existing traffic patterns
5. Clone repo and create branch
6. Make changes to files
7. Get user confirmation for changes
8. Commit and push
9. Format PR description - Include IPAM validation warnings if any
10. Get user confirmation for PR
11. Create PR

IPAM VALIDATION RULES:
- NEVER skip IPAM validation for any IP or CIDR
- If validation returns exists=False, treat as HIGH PRIORITY WARNING
- Always inform user about missing IPAM entries before proceeding
- Document all IPAM warnings in the PR description under "Risk Assessment"

IMPORTANT: Always get user confirmation before:
- Proceeding with IPs/CIDRs not in IPAM
- Making file changes
- Committing and pushing
- Creating pull requests

FORMATTING: When providing summaries, use proper formatting:
- Use line breaks between bullet points
- Use ⚠️ emoji for warnings
- Use ✅ emoji for successful validations
- Make IPAM validation results highly visible

Be concise and ask for missing information when needed.""",
    )
    logger.info(f"✅ Agent initialized with state: {agent.state.get()}")


@app.entrypoint
async def strands_agent_bedrock(payload, context):
    """
    Main entry point for the firewall-automation agent

    Args:
        payload: The input payload containing user data
        context: The runtime context object containing session information
    """
    global agent

    # Log both payload and context info
    logger.info(f"Received payload: {payload}")
    logger.info(f"Context session_id: {context.session_id}")

    user_input = payload.get("prompt")
    actor_id = payload.get("actor_id", "default_user")  # Provide default for demo
    session_id = context.session_id  # Get session_id from context

    # Validate required fields
    if user_input is None:
        error_msg = "❌ ERROR: Missing 'prompt' field in payload"
        logger.error(error_msg)
        yield error_msg

    # Initialize agent on first request
    if agent is None:
        logger.info("First request - initializing agent")
        initialize_agent(actor_id, session_id)
    else:
        logger.info("Using existing agent instance")
        # Update the session ID in case it changed
        if agent.state.get("session_id") != session_id:
            logger.info(f"Updating session ID to {session_id}")
            agent.state.set("session_id", session_id)
        if agent.state.get("actor_id") != actor_id:
            logger.info(f"Updating actor ID to {actor_id}")
            agent.state.set("actor_id", actor_id)

    agent_stream = agent.stream_async(user_input)
    tool_name = None
    try:
        async for event in agent_stream:
            # Handle streaming events from tools (like ado_git_agent)
            if tool_stream := event.get("tool_stream_event"):
                if update := tool_stream.get("data"):
                    yield update

            # Handle tool usage events
            elif (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                yield f"\n\n🔧 Using tool: {tool_name}\n\n"

            # Handle data events
            elif "data" in event:
                tool_name = None
                yield event["data"]
    except Exception as e:
        yield f"Error: {str(e)}"


if __name__ == "__main__":
    app.run()
