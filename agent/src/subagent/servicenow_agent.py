"""
ServiceNow MCP agent with integrated tools
"""

import logging
import requests
import base64
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# ServiceNow configuration
SERVICENOW_INSTANCE = "https://REPLACEME.service-now.com"
SERVICENOW_USERNAME = "admin"
SERVICENOW_PASSWORD = "REDACTED"

def get_servicenow_auth():
    """Get basic auth header for ServiceNow API"""
    credentials = f"{SERVICENOW_USERNAME}:{SERVICENOW_PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded_credentials}"}

# Integrated ServiceNow tools
def servicenow_create_change_request(short_description: str, description: str = None, change_type: str = "normal"):
    """Create a new change request in ServiceNow"""
    try:
        headers = get_servicenow_auth()
        headers["Content-Type"] = "application/json"
        
        data = {
            "short_description": short_description,
            "type": change_type,
            "state": "1"
        }
        if description:
            data["description"] = description
        
        url = f"{SERVICENOW_INSTANCE}/api/now/table/change_request"
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        return {"success": True, "result": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def servicenow_list_change_requests(limit: int = 10, state: str = None):
    """List change requests from ServiceNow"""
    try:
        headers = get_servicenow_auth()
        
        params = {
            "sysparm_limit": limit,
            "sysparm_display_value": "true"
        }
        if state:
            params["sysparm_query"] = f"state={state}"
        
        url = f"{SERVICENOW_INSTANCE}/api/now/table/change_request"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return {"success": True, "result": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def servicenow_get_change_request(change_id: str):
    """Get details of a specific change request"""
    try:
        headers = get_servicenow_auth()
        
        url = f"{SERVICENOW_INSTANCE}/api/now/table/change_request/{change_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return {"success": True, "result": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def servicenow_list_catalog_items(limit: int = 10, category: str = None):
    """List service catalog items"""
    try:
        headers = get_servicenow_auth()
        
        params = {
            "sysparm_limit": limit,
            "sysparm_display_value": "true"
        }
        if category:
            params["sysparm_query"] = f"category={category}"
        
        url = f"{SERVICENOW_INSTANCE}/api/now/table/sc_cat_item"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return {"success": True, "result": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def servicenow_get_catalog_item(item_id: str):
    """Get details of a specific catalog item"""
    try:
        headers = get_servicenow_auth()
        
        url = f"{SERVICENOW_INSTANCE}/api/now/table/sc_cat_item/{item_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return {"success": True, "result": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def servicenow_list_catalog_categories(limit: int = 10):
    """List service catalog categories"""
    try:
        headers = get_servicenow_auth()
        
        params = {
            "sysparm_limit": limit,
            "sysparm_display_value": "true"
        }
        
        url = f"{SERVICENOW_INSTANCE}/api/now/table/sc_category"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return {"success": True, "result": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Strands tools
@tool
def create_change(short_description: str, description: str = None, change_type: str = "normal"):
    """Create a new change request"""
    return servicenow_create_change_request(short_description, description, change_type)

@tool
def list_changes(limit: int = 10, state: str = None):
    """List recent change requests"""
    return servicenow_list_change_requests(limit, state)

@tool
def get_change_details(change_id: str):
    """Get details of a specific change request"""
    return servicenow_get_change_request(change_id)

@tool
def list_catalog_items_tool(limit: int = 10, category: str = None):
    """List service catalog items"""
    return servicenow_list_catalog_items(limit, category)

@tool
def get_catalog_item_tool(item_id: str):
    """Get details of a specific catalog item"""
    return servicenow_get_catalog_item(item_id)

@tool
def list_catalog_categories_tool(limit: int = 10):
    """List service catalog categories"""
    return servicenow_list_catalog_categories(limit)

model_id = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
model = BedrockModel(model_id=model_id)

agent = Agent(
    model=model,
    tools=[create_change, list_changes, get_change_details, list_catalog_items_tool, get_catalog_item_tool, list_catalog_categories_tool],
    system_prompt="""You are a ServiceNow assistant for change management and service catalog operations.

Available tools:
- create_change: Create new change requests
- list_changes: List recent change requests  
- get_change_details: Get details of specific change requests
- list_catalog_items_tool: List service catalog items
- get_catalog_item_tool: Get details of specific catalog items
- list_catalog_categories_tool: List service catalog categories

Use these tools to help users manage ServiceNow change requests and browse the service catalog effectively.""",
)

@tool
async def servicenow(prompt):
    """ServiceNow agent for change management and catalog operations"""
    if not prompt.strip():
        yield "Error: Prompt cannot be blank"
        return

    agent_stream = agent.stream_async(prompt)
    tool_name = None
    try:
        async for event in agent_stream:
            if tool_stream := event.get("tool_stream_event"):
                if update := tool_stream.get("data"):
                    yield f"\n  ↳ {update}\n"

            elif (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                yield f"\n\n  ↳ 🔧 **ServiceNow tool: {tool_name}**\n\n"

            elif "data" in event:
                tool_name = None
                yield event["data"]
    except Exception as e:
        yield f"\n\nError in ServiceNow agent: {str(e)}\n"

@app.entrypoint
async def servicenow_bedrock_agent(payload, context):
    """Main entry point for the ServiceNow Bedrock agent"""
    user_input = payload.get("prompt")
    
    if user_input is None:
        yield "❌ ERROR: Missing 'prompt' field in payload"
        return
    
    async for response in servicenow(user_input):
        yield response

if __name__ == "__main__":
    app.run()
