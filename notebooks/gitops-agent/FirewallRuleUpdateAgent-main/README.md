# GitHub Agent

An AI-powered GitHub automation agent built on AWS Bedrock AgentCore that can clone repositories, make changes, commit, push, and create pull requests automatically using natural language instructions.

## Features

- **Repository Management**: Clone repositories and create new branches
- **File Operations**: Read, write, and edit files using AI assistance
- **Git Operations**: Commit changes with descriptive messages
- **GitHub Integration**: Push changes and create pull requests automatically
- **AgentCore Deployment**: Serverless deployment on AWS Bedrock AgentCore


## Prerequisites

- Python 3.13+
- Git installed and configured
- AWS credentials configured (for Bedrock and AgentCore access)
- GitHub Personal Access Token
- Required Python packages (see Installation)

## Installation

1. Install required dependencies:
```bash
pip install strands strands-agents-tools bedrock-agentcore bedrock-agentcore-starter-toolkit
```

2. Set up environment variables:
   - `REPO_URL`: Target GitHub repository URL
   - `PAT_TOKEN`: GitHub Personal Access Token (with repo permissions)
   - `GITHUB_API_URL`: GitHub API endpoint for creating PRs
   - `VERBOSE`: Set to "true" for detailed output (optional)

3. Configure AWS credentials for Bedrock access:
```bash
aws configure
```

## Configuration

Set environment variables in `setup-env.sh`:

```bash
export REPO_URL="https://github.com/your-username/your-repo.git"
export PAT_TOKEN="your_github_pat_token_here"
export GITHUB_API_URL="https://api.github.com/repos/your-username/your-repo/pulls"
export VERBOSE="false"
```

Then source the script:

```bash
source setup-env.sh
```

## Usage

### Deploy to AgentCore

Configure the agent for AWS Bedrock AgentCore:
```bash
agentcore configure --disable-memory --entrypoint github-agent.py
```

Then deploy using:
```bash
./launch-agent.sh
```

### Invoke via API

Once deployed, invoke the agent by sending a payload with your prompt:

```bash
agentcore invoke '{"prompt": "Allow UDP traffic on port 899"}'
```

### Local Development

Run locally for testing:
```bash
python github-agent.py
```

Send a payload to the local agent
```bash
# Test with curl:
curl -X POST http://localhost:8080/invocations \
-H "Content-Type: application/json" \
-d '{"prompt": "Allow UDP traffic on port 899"}'
```

## Architecture

The agent is built using AWS Bedrock AgentCore, which provides:

- **Serverless Deployment**: No infrastructure management required
- **API Endpoint**: HTTP-based invocation for integration with other services
- **Scalability**: Automatic scaling based on demand
- **Managed Runtime**: Built-in agent execution environment

### AgentCore Entrypoint

The agent uses the `@app.entrypoint` decorator to define the invocation handler:

```python
@app.entrypoint
def invoke_agent(payload):
    prompt = payload.get("prompt", "")
    # Agent initialization and execution
    return result.message
```

## Available Tools

The agent has access to the following tools:

### Repository Operations
- `clone_repo(branch_name)`: Clone repository and create new branch
- `commit_and_push(repo_path, branch_name, commit_message)`: Commit and push changes
- `create_pull_request(branch_name, title, description)`: Create GitHub pull request

### File Operations
- `file_read`: Read file contents
- `file_write`: Write content to files
- `editor`: Interactive file editing

## Workflow

The agent follows this typical workflow:

1. **API Invocation**: Receives prompt via AgentCore API endpoint
2. **Clone Repository**: Downloads the target repository to a temporary directory
3. **Create Branch**: Creates a new feature branch for changes
4. **Make Changes**: Uses AI to understand requirements and modify files
5. **Commit Changes**: Stages and commits changes with descriptive messages
6. **Push to GitHub**: Pushes the branch to the remote repository
7. **Create Pull Request**: Opens a PR with title and description
8. **Return Result**: Sends response back through API

## Model Configuration

The agent uses AWS Bedrock with Claude 3.7 Sonnet:

```python
model_config = {
    "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "max_tokens": 64000,
    "region_name": "us-west-2"
}
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify GitHub PAT token has correct permissions
2. **AWS Errors**: Ensure AWS credentials are configured and have Bedrock access
3. **Git Errors**: Check that Git is installed and configured properly
4. **Network Issues**: Verify internet connectivity for GitHub and AWS access
5. **Deployment Issues**: Ensure bedrock-agentcore package is installed and AWS region supports AgentCore


