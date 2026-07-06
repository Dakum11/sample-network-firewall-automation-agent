# Account Details Agent Development

This folder contains resources for building the Account Details Agent.

## Overview

The Account Details Agent provides AWS account metadata by querying DynamoDB:
- AWS Account ID
- Account Name
- VPC CIDR ranges
- Environment tags
- Owner information

## Related Jira Tasks

- **FWAUTO-16**: Account Details Agent implementation (Phase 2)

## Getting Started

This folder doesn't have sample notebooks yet. Reference:
- **`../supervisor-agent/`** - For agent creation patterns
- **`../firewall-logs-tool/network_firewall_analyser_agent.py`** - For tool definition examples and DynamoDB integration patterns

## Key Components to Build

### Tool Definitions

```python
@tool
def get_account_by_name(account_name: str) -> dict:
    """
    Get AWS account details by account name (supports partial matching)

    Args:
        account_name: Full or partial account name (e.g., "prod", "RT-Prod")

    Returns:
        Account ID, CIDR, environment, owner details
    """
    # Query DynamoDB with fuzzy matching
    # Return structured account info
```

```python
@tool
def get_account_by_id(account_id: str) -> dict:
    """
    Get AWS account details by account ID

    Args:
        account_id: 12-digit AWS account ID

    Returns:
        Full account metadata
    """
    # Direct DynamoDB lookup by primary key
```

```python
@tool
def get_account_by_cidr(cidr: str) -> list:
    """
    Find accounts matching a CIDR range

    Args:
        cidr: CIDR notation (e.g., "10.10.0.0/16")

    Returns:
        List of matching accounts
    """
    # Query DynamoDB GSI or scan with filter
```

## DynamoDB Integration

### Table Structure (Example)
```python
{
    "account_id": "123456789012",  # Primary key
    "account_name": "RT-Prod",
    "cidr_ranges": ["10.10.0.0/16", "10.11.0.0/16"],
    "environment": "production",
    "owner_team": "Platform Team",
    "owner_email": "platform-team@example.com",
    "tags": {
        "CostCenter": "IT-INFRA",
        "Region": "ap-southeast-2"
    }
}
```

### Cross-Account Access Pattern
Similar to the OpenSearch example in firewall-logs-tool:

```python
def initialize_dynamodb(table_name, region, role_arn):
    """Initialize DynamoDB client with cross-account role"""
    sts_client = boto3.client("sts", region_name=region)

    response = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName="AccountDetailsAgent"
    )

    credentials = response["Credentials"]

    dynamodb = boto3.resource(
        'dynamodb',
        region_name=region,
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )

    return dynamodb.Table(table_name)
```

## Caching Strategy

```python
from datetime import datetime, timedelta

# In-memory cache with TTL
account_cache = {}
CACHE_TTL = timedelta(minutes=5)

def get_cached_account(account_id: str) -> Optional[dict]:
    """Get account from cache if not expired"""
    if account_id in account_cache:
        cached_data, cached_time = account_cache[account_id]
        if datetime.now() - cached_time < CACHE_TTL:
            return cached_data
    return None

def cache_account(account_id: str, data: dict):
    """Store account in cache"""
    account_cache[account_id] = (data, datetime.now())
```

## Fuzzy Matching

```python
from fuzzywuzzy import fuzz

def find_accounts_by_partial_name(partial_name: str, accounts: list) -> list:
    """
    Find accounts using fuzzy string matching

    Args:
        partial_name: Partial account name
        accounts: List of all accounts from DynamoDB

    Returns:
        List of matches sorted by relevance
    """
    matches = []

    for account in accounts:
        account_name = account['account_name']

        # Calculate similarity scores
        ratio = fuzz.ratio(partial_name.lower(), account_name.lower())
        partial_ratio = fuzz.partial_ratio(partial_name.lower(), account_name.lower())

        # Use the higher score
        score = max(ratio, partial_ratio)

        if score > 60:  # Threshold for match
            matches.append((account, score))

    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)

    return [account for account, score in matches]
```

## Implementation Tips

- **Partial Name Matching**: "prod" should match "RT-Prod", "RT-Prod-Web", etc.
- **Did You Mean?**: Provide suggestions when no exact match: "Did you mean RT-Prod or RT-Prod-DR?"
- **Multiple Matches**: When multiple accounts match, return all with scores
- **Case Insensitive**: Always normalize to lowercase for matching
- **Null Handling**: Return gracefully when account not found (don't raise errors)
- **Batch Queries**: Use `batch_get_item` when fetching multiple accounts

## Integration with Other Agents

The Account Details Agent is called by:
- **Supervisor Agent**: To enrich user queries ("RT-Prod" → account ID + CIDR)
- **Firewall Logs Agent**: To resolve account names in log queries
- **GitSecOps Agent**: To get source CIDR for rule generation
- **SNOW Agent**: To cross-reference accounts with CMDB CIs

## Example Workflow

```
User: "Show me blocked traffic from prod"
  ↓
Supervisor Agent → Account Details Agent: get_account_by_name("prod")
  ↓
Account Details Agent returns:
{
    "matches": [
        {
            "account_id": "123456789012",
            "account_name": "RT-Prod",
            "cidr": "10.10.0.0/16",
            "confidence": 0.95
        },
        {
            "account_id": "987654321098",
            "account_name": "RT-Prod-DR",
            "cidr": "10.20.0.0/16",
            "confidence": 0.85
        }
    ]
}
  ↓
Supervisor Agent → Clarify with user which account
  OR
Supervisor Agent → Firewall Logs Agent: search both accounts
```

## Testing

1. **Query Performance**: Measure DynamoDB query latency
2. **Cache Hit Rate**: Track how often cache is used
3. **Fuzzy Match Accuracy**: Test with common typos and partial names
4. **Cross-Account Access**: Verify role assumption works
5. **Error Scenarios**: Test when DynamoDB unavailable

## References

- Jira Task: FWAUTO-16
- DynamoDB boto3 Documentation
- fuzzywuzzy Library: https://github.com/seatgeek/fuzzywuzzy
- See `../firewall-logs-tool/network_firewall_analyser_agent.py` for DynamoDB initialization pattern
