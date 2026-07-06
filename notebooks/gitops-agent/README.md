# GitOps Agent Development

This folder contains resources for building the Firewall GitSecOps Agent.

## Overview

The GitSecOps Agent handles firewall rule generation and Git operations:

**Phase 1 (FWAUTO-14)**:
- Clone SecOps Git repository
- Read existing Suricata rules
- Create Git branches
- Generate new rules
- Commit changes
- Push to Azure DevOps

**Phase 2 (FWAUTO-19)**:
- Create pull requests with metadata
- Fillout the firewall change request document

## Related Jira Tasks

- **FWAUTO-14**: Firewall GitSecOps agent implementation (Phase 1)
- **FWAUTO-19**: Enhance GitSecOps Agent - PR creation and automation (Phase 2)

## Getting Started

This folder doesn't have sample notebooks yet. Reference the firewall-logs-tool agent example for agent structure patterns.

## Key Components to Build

### Phase 1: Rule Generation

1. **Git Clone Tool**
   ```python
   @tool
   def clone_firewall_rules_repo() -> dict:
       """Clone the SecOps repository from Azure DevOps"""
       # Get PAT from Secrets Manager
       # Clone to /tmp/firewall-rules-{uuid}
       # Return repo path
   ```

2. **Rule Reading Tool**
   ```python
   @tool
   def read_existing_rules(rule_type: str) -> list:
       """Read existing Suricata rules for duplicate detection"""
       # Parse rule files
       # Return list of existing rules
   ```

3. **Rule Generation Tool**
   ```python
   @tool
   def generate_suricata_rule(
       action: str,  # pass/drop
       protocol: str,  # tls/http
       source: str,  # CIDR from Account Details Agent
       destination: str,  # domain/IP
       port: int,
       metadata: dict  # SRA, account, justification
   ) -> dict:
       """Generate a Suricata firewall rule"""
       # Format rule with metadata comments
       # Validate syntax
       # Check for duplicates
       # Return rule + file path
   ```

### Phase 2: PR Automation

4. **Branch Creation Tool**
   ```python
   @tool
   def create_feature_branch(branch_name: str) -> dict:
       """Create a feature branch for the rule change"""
       # Branch from main
       # Use naming convention: firewall/{action}-{protocol}-{account}
   ```

5. **Commit and Push Tool**
   ```python
   @tool
   def commit_and_push_rule(
       rule_file: str,
       rule_content: str,
       commit_message: str
   ) -> dict:
       """Commit rule change and push to Azure DevOps"""
       # Write rule file
       # Git add, commit, push
       # Return commit SHA
   ```

6. **PR Creation Tool**
   ```python
   @tool
   def create_pull_request(
       branch_name: str,
       metadata: dict  # SRA, account, CI info, justification
   ) -> dict:
       """Create PR in Azure DevOps with full metadata"""
       # Use Azure DevOps REST API
       # Fill PR template
       # Assign reviewers
       # Return PR URL
   ```

## Suricata Rule Format

```
# Metadata
# SRA: SRA-12345
# Account: RT-Prod (123456789012)
# Justification: Allow API access for prod web servers
# Created: 2025-01-15
# Created-By: Firewall Automation Chatbot

pass tls $HOME_NET any -> $EXTERNAL_NET 443 (msg:"Allow HTTPS to api.example.com"; tls.sni; content:"api.example.com"; sid:1000001; rev:1;)
```

## Key Design Decisions

### Branch Naming Convention
```
firewall/allow-tls-rtprod-apiexample
firewall/drop-http-rtdev-suspicious
```

### Commit Message Format
```
Add firewall rule: Allow HTTPS to api.example.com

SRA: SRA-12345
Account: RT-Prod (123456789012)
Source: 10.10.0.0/16 (RT-Prod VPC)
Destination: api.example.com
Action: pass
Protocol: TLS
Port: 443

Justification: Required for prod web servers to access API

Co-Authored-By: Firewall Automation Chatbot <noreply@example.com>
```

### Reviewer Assignment Logic
- **Standard rules** (allow to known domains): 1 reviewer from security team
- **High-risk rules** (allow to IPs, non-standard ports): 2 reviewers + manager approval

## Security Considerations

- **Store Azure DevOps PAT** in AWS Secrets Manager (`firewall-chatbot/azure-devops/pat`)
- **Limit PAT scope**: Code (read/write), Pull Requests (read/write) only
- **No admin permissions**: No delete, force push, or admin access
- **Automatic rotation**: 90-day expiration with alerts
- **Audit logging**: Log all Git operations with user context
- **Ephemeral storage**: Clean up `/tmp` directories after each operation

## Integration with Other Agents

The GitSecOps Agent receives information from:
- **Account Details Agent**: Provides source CIDR for rules
- **SNOW Agent**: Provides CI information for PR metadata (Phase 2)
- **Supervisor Agent**: Coordinates the full workflow

## Testing Strategy

1. **Unit Tests**:
   - Rule generation logic
   - Syntax validation
   - Duplicate detection

2. **Integration Tests** (with mocked Git):
   - Branch creation
   - Commit message formatting
   - PR template population

3. **E2E Tests** (in dev environment):
   - Full workflow from user request to PR
   - Reviewer assignment
   - Error handling

## References

- Jira Tasks: FWAUTO-14, FWAUTO-19
- GitOps Repository: Azure DevOps (see FWAUTO-24 for setup)
- GitPython Documentation: https://gitpython.readthedocs.io
- Azure DevOps REST API: https://learn.microsoft.com/en-us/rest/api/azure/devops/
- Suricata Rule Syntax: https://docs.suricata.io/en/latest/rules/
