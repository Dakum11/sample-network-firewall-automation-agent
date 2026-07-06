# AWS Network Firewall Automation Agent

A multi-agent system that automates AWS Network Firewall rule management using Amazon Bedrock AgentCore, Strands Agents SDK, and a Streamlit chat interface. Five specialist agents collaborate to validate, author, and deploy firewall rule changes — removing manual toil while preserving approval gates.

![Architecture](docs/architecture-diagram.png)

## Why This Solution?

- **Eliminates manual rule authoring** — Natural-language requests are translated into validated Suricata rules, reducing misconfiguration risk
- **End-to-end automation** — From request through IP validation, rule generation, Git commit, PR creation, and ServiceNow ticketing — all in one conversation
- **Multi-agent specialization** — Each agent is expert in one domain (account context, log analysis, IPAM, Git, ITSM) so the system scales with your operational surface
- **Approval gates preserved** — Automation handles everything *except* the human approval step, keeping change control intact
- **Conversation memory** — AgentCore Memory provides persistent multi-turn context so engineers can iterate across sessions
- **Portable GitOps** — Ships with Azure DevOps integration; swap to GitHub or GitLab by replacing one tool module

## Key Features

🤖 **Multi-Agent Orchestration**
- Supervisor agent with tool-use routing to 5 specialist sub-agents
- Built on Strands Agents SDK with Amazon Bedrock AgentCore runtime
- Automatic context assembly from account metadata, logs, and IPAM

🔥 **Firewall Rule Lifecycle**
- Suricata rule generation from natural-language descriptions
- IP/CIDR validation against enterprise IPAM (EfficientIP SOLIDserver)
- Rule syntax validation before commit

🔀 **GitSecOps Integration**
- Clone, branch, commit, push, and PR creation via Azure DevOps REST API
- PR descriptions auto-generated from structured templates
- Supports any Git provider with minimal tool replacement

📊 **Observability & Context**
- Firewall log queries via OpenSearch (alert, flow, TLS logs)
- Account metadata enrichment from DynamoDB
- Full conversation history via AgentCore Memory

🖥️ **Production-Ready UI**
- Streamlit chat interface with SSO (Cognito + Azure AD federation)
- Deployed on ECS Fargate behind an internal ALB
- Dark/light mode with conversation management

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Streamlit Web UI                             │
│                    (ECS Fargate + Cognito SSO)                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ InvokeAgentRuntime API
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Bedrock AgentCore Runtime                         │
│              ┌──────────────────────────────────┐                   │
│              │       Supervisor Agent            │                   │
│              │    (Strands SDK + Claude)         │                   │
│              └──────────┬───────────────────────┘                   │
│                         │                                           │
│         ┌───────┬───────┼───────┬───────────┐                      │
│         ▼       ▼       ▼       ▼           ▼                      │
│   ┌─────────┐ ┌─────┐ ┌─────┐ ┌──────┐ ┌───────┐                  │
│   │Account  │ │Logs │ │Git  │ │IPAM  │ │Service│                  │
│   │Details  │ │Agent│ │SecOps│ │Agent │ │Now    │                  │
│   └────┬────┘ └──┬──┘ └──┬──┘ └──┬───┘ └───┬───┘                  │
│        │         │       │       │         │                       │
└────────┼─────────┼───────┼───────┼─────────┼───────────────────────┘
         │         │       │       │         │
         ▼         ▼       ▼       ▼         ▼
    ┌────────┐ ┌───────┐ ┌─────┐ ┌────┐ ┌───────┐
    │DynamoDB│ │Open   │ │Azure│ │IPAM│ │Service│
    │        │ │Search │ │DevOps│ │API │ │Now    │
    └────────┘ └───────┘ └─────┘ └────┘ └───────┘
```

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Python | 3.11 | Agent and application runtime |
| uv | 0.4+ | Python package management |
| Docker | 24.0+ | Container builds |
| AWS CLI | 2.15+ | AWS resource management |
| AWS Account | — | Bedrock AgentCore, ECR, ECS, DynamoDB, OpenSearch |
| Bedrock Model Access | — | Claude Sonnet 4 (via inference profile) |
| Azure DevOps | — | Git repository for firewall rules (or swap for GitHub) |

## Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/aws-samples/aws-network-firewall-automation-agent.git
   cd aws-network-firewall-automation-agent
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your AWS account, AgentCore, and Azure DevOps settings
   ```

3. **Deploy the AgentCore runtime**

   ```bash
   cd agent
   python deploy.py
   ```

4. **Build and push the agent container**

   ```bash
   cd agent/src
   uv sync
   docker build -t firewall-automation-agent:latest .
   # Tag and push to your ECR repository
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   docker tag firewall-automation-agent:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/firewall-automation-agent:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/firewall-automation-agent:latest
   ```

5. **Deploy the Streamlit UI (CloudFormation)**

   ```bash
   aws cloudformation deploy \
     --template-file infra/cloudformation/app-template.yaml \
     --stack-name firewall-automation-app \
     --parameter-overrides \
       ProjectName=firewall-automation \
       VpcId=vpc-xxx \
       SubnetIds=subnet-xxx,subnet-yyy \
       ContainerImage=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/firewall-automation-agent:latest \
       WebConsoleRootDomainName=firewall.example.com \
       HostedZoneId=ZXXXXXXXXXXXXX \
       AzureADTenantId=your-tenant-id \
       AzureADClientId=your-client-id \
       AzureADClientSecret=your-secret \
     --capabilities CAPABILITY_NAMED_IAM
   ```

6. **Run locally (development)**

   ```bash
   cd app
   uv sync
   uv run streamlit run app.py
   ```

## Environment Variables

### AWS & AgentCore

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_REGION` | Yes | AWS region for all services |
| `BEDROCK_MODEL_ID` | Yes | Inference profile ID (e.g., `us.anthropic.claude-sonnet-4-20250514-v1:0`) |
| `AGENTCORE_MEMORY_ID` | No | AgentCore Memory ID for conversation persistence |
| `AGENT_RUNTIME_ID` | Yes | AgentCore Runtime ID from deployment |
| `AGENT_SUBNETS` | Yes | Comma-separated subnet IDs for AgentCore VPC |
| `AGENT_SECURITY_GROUPS` | Yes | Comma-separated security group IDs |
| `AGENT_EXECUTION_ROLE_NAME` | No | IAM role name for AgentCore (default: auto-generated) |

### Azure DevOps (GitSecOps)

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_DEVOPS_ORG` | Yes | Azure DevOps organization name |
| `AZURE_DEVOPS_PROJECT` | Yes | Azure DevOps project name |
| `REPO_NAME` | Yes | Git repository containing firewall rules |
| `AZURE_DEVOPS_SECRET_NAME` | No | Secrets Manager secret name for PAT (default: `firewall-automation/azure-devops/pat`) |

### Backend Services

| Variable | Required | Description |
|----------|----------|-------------|
| `CROSS_ACCOUNT_ROLE_ARN` | No | IAM role ARN for cross-account DynamoDB access |
| `DYNAMODB_ACCOUNT_METADATA_TABLE_NAME` | No | DynamoDB table name (default: `account-metadata`) |
| `IPAM_SECRET_NAME` | No | Secrets Manager secret for IPAM credentials |
| `ECR_REPOSITORY` | Yes | ECR repository URI for agent container |

## Project Structure

```
aws-network-firewall-automation-agent/
├── agent/
│   ├── src/
│   │   ├── agent.py              # Supervisor agent (Strands SDK entry point)
│   │   ├── subagent/
│   │   │   └── gitops_tools.py   # Azure DevOps Git operations
│   │   ├── utils/
│   │   │   ├── account_details_utils.py  # DynamoDB account lookup
│   │   │   └── ipam_utils.py     # IPAM IP/CIDR validation
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── deploy.py                 # AgentCore deployment script
│   └── deploy.sh                 # Shell wrapper for deployment
├── app/
│   ├── app.py                    # Streamlit web UI
│   ├── static/                   # UI assets (logos, icons)
│   ├── Dockerfile
│   └── pyproject.toml
├── infra/
│   ├── cloudformation/
│   │   └── app-template.yaml     # ECS Fargate + ALB + Cognito stack
│   └── bicep/
│       └── app-registration.bicep  # Azure AD app registration
├── notebooks/                    # Individual agent development notebooks
│   ├── account-details-agent/
│   ├── firewall-logs-agent/
│   ├── gitops-agent/
│   ├── ipam-agent/
│   ├── snow-agent/
│   ├── agentcore-identity/
│   └── monitoring/
├── sample-data/
│   ├── dynamodb-account-metadata.json
│   ├── opensearch-index-mapping.json
│   └── suricata-rules-example.rules
├── docs/
│   └── architecture-diagram.html
├── .github/workflows/
│   ├── deploy.yml                # App CI/CD pipeline
│   └── deploy-agent.yml          # Agent CI/CD pipeline
├── .env.example
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── LICENSE
├── NOTICE
└── README.md
```

## Customization

### Swapping Git Providers

The GitSecOps agent uses Azure DevOps REST APIs via `agent/src/subagent/gitops_tools.py`. To switch to GitHub or GitLab:

1. Replace the tool functions (`clone_repo`, `commit_and_push`, `create_pull_request`) with your provider's API calls
2. Update the environment variables for authentication (e.g., `GITHUB_TOKEN` instead of Azure DevOps PAT)
3. The supervisor agent's tool routing requires no changes — it calls tools by name regardless of backend

### Adding New Sub-Agents

1. Create a new tool function in `agent/src/subagent/` or `agent/src/utils/`
2. Decorate with `@tool` from Strands Agents SDK
3. Register the tool in `agent/src/agent.py` tools list
4. The supervisor will automatically discover and route to the new tool based on its docstring

### Customizing the IPAM Backend

The default integration targets EfficientIP SOLIDserver. To use a different IPAM:

1. Update `agent/src/utils/ipam_utils.py` with your IPAM's REST API endpoints
2. Store credentials in AWS Secrets Manager under the key specified by `IPAM_SECRET_NAME`
3. Expected secret format: `{"username": "...", "password": "...", "ipam_url": "https://..."}`

### Modifying the Firewall Rule Format

Sample Suricata rules are in `sample-data/suricata-rules-example.rules`. The agent generates rules matching this format. To change the rule syntax or add custom metadata fields, update the supervisor agent's system prompt in `agent/src/agent.py`.

## Cost Estimation

| Service | Configuration | Estimated Monthly Cost |
|---------|--------------|----------------------|
| Amazon Bedrock (Claude Sonnet) | ~1,000 conversations/month | $50–$150 |
| Bedrock AgentCore Runtime | 1 runtime + 1 endpoint | $0 (preview pricing) |
| ECS Fargate | 0.5 vCPU, 1 GB (Streamlit UI) | ~$15 |
| Application Load Balancer | 1 ALB + data processing | ~$20 |
| Amazon Cognito | Up to 50,000 MAUs | $0 (free tier) |
| DynamoDB | On-demand, <1 GB storage | ~$1 |
| OpenSearch Serverless | 1 collection (if self-hosted) | ~$175 |
| ECR | <5 GB storage | ~$0.50 |
| Secrets Manager | 3–5 secrets | ~$2 |
| **Total** | | **~$265–$365/month** |

> **Note:** Costs vary significantly based on conversation volume, Bedrock model usage, and whether you use existing OpenSearch/IPAM infrastructure. AgentCore pricing may change after preview.

## Cleanup

```bash
# Delete CloudFormation stack (ECS, ALB, Cognito)
aws cloudformation delete-stack --stack-name firewall-automation-app

# Delete AgentCore resources
aws bedrock-agentcore-control delete-agent-runtime-endpoint \
  --agent-runtime-id <RUNTIME_ID> \
  --endpoint-name <ENDPOINT_NAME> \
  --region us-east-1

aws bedrock-agentcore-control delete-agent-runtime \
  --agent-runtime-id <RUNTIME_ID> \
  --region us-east-1

aws bedrock-agentcore-control delete-memory \
  --memory-id <MEMORY_ID> \
  --region us-east-1

# Delete ECR repository
aws ecr delete-repository \
  --repository-name firewall-automation-agent \
  --region us-east-1 \
  --force

# Delete IAM role
aws iam delete-role-policy \
  --role-name FirewallAutomation-AgentCore-Execution-Role \
  --policy-name AgentPermissions
aws iam delete-role \
  --role-name FirewallAutomation-AgentCore-Execution-Role
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
