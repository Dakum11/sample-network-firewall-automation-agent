"""
ADO Agent - AI-powered Git automation using AWS Bedrock AgentCore.

This agent can clone repositories, make changes, commit, push, and create pull requests
automatically using natural language instructions.
"""

from pprint import pp
import os
import boto3
import subprocess
import tempfile
from pathlib import Path

import requests
from strands import Agent
from strands.models import BedrockModel
from strands.tools import tool
from strands_tools import editor, file_read, file_write

from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Initialize AgentCore application
app = BedrockAgentCoreApp()

# Bypass tool consent for automated execution
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Disable editor tool creating .bak files
os.environ["EDITOR_DISABLE_BACKUP"] = "true"

# Load configuration from environment variables
REPO_URL = os.getenv("REPO_URL", "https://pace-devops.visualstudio.com/_git/IaC-AWS-Firewall-Automation")

# TODO Secrets manager
def get_secret(secret_name: str) -> str:
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

PAT_TOKEN = os.getenv("PAT_TOKEN", "")
#GITHUB_API_URL = os.getenv("GITHUB_API_URL", "")
VERBOSE = os.getenv("VERBOSE", "false").lower() == "true"

response = get_secret("firewall-chatbot/azure-devops/pat")
print(response)

SYSTEM_PROMPT = f"""You are a ADO automation agent. Your task is to:
1. Clone the repository {REPO_URL}
2. Create a new branch for the changes
3. Make the changes requested by the user
4. Commit the changes
5. Push to GitHub


Use the provided tools to accomplish these tasks."""

#6. Create a pull request


@tool
def clone_repo(branch_name: str) -> str:
    """Clone the repository and create a new branch.

    Args:
        branch_name: Name for the new branch

    Returns:
        Path to the cloned repository
    """
    # Create temporary directory for repository
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir) / "network-firewall"
    if VERBOSE:
        print(repo_path)

    # Clone repository using PAT authentication
    auth_url = REPO_URL.replace("https://", f"https://{PAT_TOKEN}@")
    subprocess.run(
        ["git", "clone", auth_url, str(repo_path)],
        check=True,
        capture_output=not VERBOSE,
    )
    
    # Create and checkout new branch
    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=repo_path,
        check=True,
        capture_output=not VERBOSE,
    )

    return str(repo_path)


@tool
def commit_and_push(repo_path: str, branch_name: str, commit_message: str) -> str:
    """Commit changes and push to GitHub.

    Args:
        repo_path: Path to the repository
        branch_name: Name of the branch
        commit_message: Commit message

    Returns:
        Success message
    """
    # Stage all changes
    subprocess.run(
        ["git", "add", "."], cwd=repo_path, check=True, capture_output=not VERBOSE
    )
    
    # Commit with message
    subprocess.run(
        ["git", "commit", "-m", commit_message],
        cwd=repo_path,
        check=True,
        capture_output=not VERBOSE,
    )
    
    # Push to remote branch
    subprocess.run(
        ["git", "push", "origin", branch_name],
        cwd=repo_path,
        check=True,
        capture_output=not VERBOSE,
    )

    return f"Changes committed and pushed to branch {branch_name}"


# @tool
# def create_pull_request(branch_name: str, title: str, description: str) -> str:
#     """Create a pull request using ADO API.

#     Args:
#         branch_name: Source branch name
#         title: PR title
#         description: PR description

#     Returns:
#         PR URL or error message
#     """
#     # Prepare GitHub API request
#     url = GITHUB_API_URL
#     headers = {
#         "Authorization": f"Bearer {PAT_TOKEN}",
#         "Accept": "application/vnd.github.v3+json",
#     }
#     data = {"title": title, "body": description, "head": branch_name, "base": "main"}

#     # Create pull request
#     response = requests.post(url, headers=headers, json=data)
#     if response.status_code == 201:
#         pr_url = response.json()["html_url"]
#         return f"Pull request created: {pr_url}"
#     else:
#         return f"Failed to create PR: {response.text}"


@app.entrypoint
def invoke_agent(payload):
    """AgentCore entrypoint for handling agent invocations.
    
    Args:
        payload: Dictionary containing the prompt 
        
    Returns:
        Agent response message
    """
    prompt = payload.get("prompt", "")
    
    if not prompt.strip():
        return "Error: Prompt cannot be blank"

    # Configure Bedrock model
    model_config = {
        "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "max_tokens": 64000,
        "region_name": "us-west-2",
    }
    MODEL = BedrockModel(**model_config)

    # Initialize agent with tools and system prompt
    agent = Agent(
        model=MODEL,
        system_prompt=SYSTEM_PROMPT,
        messages=[],
        tools=[
            clone_repo,
            commit_and_push,
            #create_pull_request,
            editor,
            file_read,
            file_write,
        ],
    )

    # Execute agent with user prompt
    result = agent(prompt)
    return result.message


# if __name__ == "__main__":
#     # Run AgentCore application
#     app.run()

