# IPAM Agent

An automation agent that validates whether a given **CIDR or IP address** is already allocated in the IPAM system. It connects to an EfficientIP-based IPAM server and checks allocation status, providing owner and region details when available. It exposes one primary tool: `validate_ip_addresses`.

---

## Features

- **CIDR/IP Validation**: Checks if a given IP address or subnet is already in use
- **Owner/Region Extraction**: Parses metadata (`owner`, `region`) from IPAM class parameters
- **Free vs Allocated Detection**: Differentiates free vs assigned states
- **Subnet Awareness**: Detects parent subnet info when IP is free
- **Extendable**: Designed for integration with PR validation or network automation flows

---

## Prerequisites

- Python 3.10+
- EfficientIP IPAM server with REST API access
- Valid IPAM credentials (base64-encoded)
- Required Python packages (see below)

---

## Installation

1. Install the required Python libraries:

```bash
pip install strands strands-agents-tools bedrock-agentcore bedrock-agentcore-starter-toolkit
```

2. Set up environment variables:
   - `SOLIDSERVER_URL`: IPAM SolidServer URL
   - `USERNAME`: Login Username
   - `PASSWORD`: Login Password
   - `VERBOSE`: Set to "true" for detailed output (optional)

3. Configure AWS credentials for Bedrock access:
```bash
aws configure
```

## Configuration

Set environment variables in `setup-env.sh`:

```bash
export SOLIDSERVER_URL="https://your-ipam-server.example.com"
export USERNAME="ipam_login_username"
export PASSWORD="ipam_login_password"
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
agentcore configure --disable-memory --entrypoint ipam_agent.py
```

Then deploy using:
```bash
./launch-agent.sh
```

### Invoke via API

Once deployed, invoke the agent by sending a payload with your prompt:

```bash
agentcore invoke '{"prompt": "Check if 10.10.128.24/30 is allocated"}'
```

### Local Development

Run locally for testing:
```bash
python ipam_agent.py
```

Send a payload to the local agent
```bash
# Test with curl:
curl -X POST http://localhost:8080/invocations \
-H "Content-Type: application/json" \
-d '{"prompt": "Check if 10.10.128.24/30 is allocated"}'
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
- `validate_ip_addresses`: Validate IP addresses and CIDR ranges using AWS VPC IPAM.

## Workflow

The agent follows this typical workflow:
1. **API Invocation**: Receives an IP address or CIDR range through the AgentCore API endpoint
2. **Input Parsing**: Distinguishes between single IPs and CIDR blocks for validation
3. **CIDR/IP Lookup**: Queries the IPAM server via REST API to check if the address or subnet already exists
4. **Ownership Resolution**: If found, extracts metadata like owner and region from class parameters
5. **Free IP/Subnet Evaluation**: If not found, checks if the address is within a known subnet or offers free subnet suggestions
6. **Result Formatting**: Converts the findings into a human-readable summary (e.g., "The CIDR 10.9.56.0/24 is owned by Cloud Infra")
7. **Return Response**: Sends the structured response back through the AgentCore API


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

1. **Connection Errors**: Verify the IPAM System is reachable
2. **AWS Errors**: Ensure AWS credentials are configured and have Bedrock access
3. **Network Issues**: Verify internet connectivity for IPAM and AWS access
4. **Deployment Issues**: Ensure bedrock-agentcore package is installed and AWS region supports AgentCore

