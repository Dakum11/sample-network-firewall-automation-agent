#!/usr/bin/env python3
"""
Modular Account Details Agent using AWS Strands SDK
Clean separation of concerns for better maintainability and PR review
"""

import logging
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

# Import the account details tool
from account_details_tool import query_account_details

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

def initialize_agent():
    """Initialize the Strands agent with account details tool"""
    try:
        model_id = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
        model = BedrockModel(model_id=model_id)
        
        agent = Agent(
            model=model,
            tools=[query_account_details],
            system_prompt="""You are an Account Details Agent that provides AWS account information from DynamoDB.

You can search by:
- Account ID (12-digit number)
- VPC name (exact or partial match)
- CIDR range (exact or partial match)

When providing results, format them clearly and mention the match type and confidence score if available.
Include subnet details when available to help users understand the network structure."""
        )
        
        logger.info("Strands agent initialized successfully")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to initialize agent: {str(e)}")
        raise

# Initialize the agent
agent = initialize_agent()

@app.entrypoint
async def strands_agent_bedrock(payload):
    """Invoke the agent with a payload"""
    try:
        logger.info(f"Received payload: {payload}")
        user_input = payload.get("prompt", "")
        
        if not user_input:
            yield "Please provide a prompt."
            return
        
        agent_stream = agent.stream_async(user_input)
        
        async for event in agent_stream:
            if "data" in event:
                yield event["data"]
                
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        yield f"Error: {str(e)}"

if __name__ == "__main__":
    logger.info("Starting Modular Account Details Agent...")
    app.run()