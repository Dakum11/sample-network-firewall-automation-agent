# ServiceNow (SNOW) Agent Development

This folder contains resources for building the Firewall SNOW Agent.

## Overview

The SNOW Agent integrates with ServiceNow CMDB to:

**Phase 2 (FWAUTO-17)**:
- Query configuration items (CIs)
- Verify affected systems
- Prepare metadata for firewall changes

**Phase 3 (FWAUTO-22)**:
- Create ServiceNow Change Requests (CHG)
- Link CIs to change requests
- Populate change documentation

## Related Jira Tasks

- **FWAUTO-17**: Firewall SNOW Agent implementation (Phase 2)
- **FWAUTO-22**: Enhance Firewall SNOW Agent - Create CHG Requests (Phase 3)

## Getting Started

This folder doesn't have sample notebooks yet. Reference the firewall-logs-tool agent for tool definition patterns.

## Key Components to Build

### Phase 2: CMDB Queries

```python
@tool
def search_configuration_items(
    search_query: str,
    ci_class: str = "cmdb_ci_server"
) -> list:
    """
    Search ServiceNow CMDB for configuration items

    Args:
        search_query: CI name, hostname, or IP address
        ci_class: CI class to search (default: servers)

    Returns:
        List of matching CIs with sys_id, name, status, IP, account
    """
    # Query ServiceNow Table API
    # Parse response
    # Return structured CI data
```

```python
@tool
def get_ci_details(sys_id: str) -> dict:
    """
    Get detailed information about a specific CI

    Args:
        sys_id: ServiceNow sys_id of the CI

    Returns:
        Complete CI details including:
        - Name, IP, hostname
        - AWS account, VPC
        - Status, owner, support group
        - Business service, application
    """
    # GET /api/now/table/cmdb_ci/{sys_id}
```

```python
@tool
def get_ci_relationships(sys_id: str) -> dict:
    """
    Get CI relationships (depends on, used by, etc.)

    Args:
        sys_id: ServiceNow sys_id of the CI

    Returns:
        Related CIs and dependency information
    """
    # Query CI relationship table
```

### Phase 3: Change Request Creation

```python
@tool
def create_change_request(
    short_description: str,
    description: str,
    affected_cis: list,
    justification: str,
    sra_number: str,
    change_type: str = "standard"
) -> dict:
    """
    Create a ServiceNow Change Request for firewall rule change

    Args:
        short_description: Brief summary of the change
        description: Detailed description with rule info
        affected_cis: List of CI sys_ids
        justification: Business justification
        sra_number: Security risk acceptance number
        change_type: "standard" or "emergency"

    Returns:
        CHG number, sys_id, and URL
    """
    # POST /api/now/table/change_request
    # Include all required fields
    # Link affected CIs
```

## ServiceNow Integration

### Authentication
```python
import boto3
from requests.auth import HTTPBasicAuth

def get_servicenow_credentials():
    """Get ServiceNow credentials from Secrets Manager"""
    secrets_client = boto3.client('secretsmanager')

    response = secrets_client.get_secret_value(
        SecretId='firewall-chatbot/servicenow/credentials'
    )

    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']

# Use with requests
username, password = get_servicenow_credentials()
auth = HTTPBasicAuth(username, password)
```

### Table API Query Example
```python
import requests

def search_cmdb(query: str):
    """Search CMDB using Table API"""
    base_url = "https://your-instance.service-now.com"
    endpoint = "/api/now/table/cmdb_ci_server"

    params = {
        'sysparm_query': f'nameLIKE{query}^ORip_addressLIKE{query}',
        'sysparm_fields': 'sys_id,name,ip_address,u_aws_account,operational_status',
        'sysparm_limit': 10
    }

    username, password = get_servicenow_credentials()

    response = requests.get(
        f"{base_url}{endpoint}",
        auth=HTTPBasicAuth(username, password),
        params=params,
        headers={'Accept': 'application/json'}
    )

    if response.status_code == 200:
        return response.json()['result']
    else:
        raise Exception(f"ServiceNow API error: {response.status_code}")
```

## CI Query Patterns

### By Name
```
nameLIKE{query}
```

### By IP Address
```
ip_addressLIKE{query}
```

### By AWS Account
```
u_aws_account={account_id}
```

### Multiple Conditions
```
nameLIKE{query}^ORip_addressLIKE{query}^operational_status=1
```

## Caching Strategy

```python
from datetime import datetime, timedelta

# Cache CI lookups for 15 minutes
ci_cache = {}
CACHE_TTL = timedelta(minutes=15)

def get_cached_ci(ci_identifier: str) -> Optional[dict]:
    """Get CI from cache if not expired"""
    if ci_identifier in ci_cache:
        cached_data, cached_time = ci_cache[ci_identifier]
        if datetime.now() - cached_time < CACHE_TTL:
            logger.debug(f"Cache hit for CI: {ci_identifier}")
            return cached_data
    return None
```

## Error Handling

```python
def search_ci_with_retry(query: str, max_retries: int = 3):
    """Search CI with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return search_cmdb(query)
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Timeout, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception("ServiceNow API unavailable after retries")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("ServiceNow authentication failed")
            elif e.response.status_code == 429:
                # Rate limit hit
                time.sleep(5)
            else:
                raise
```

## Fuzzy Matching for CIs

```python
def find_ci_with_suggestions(query: str) -> dict:
    """
    Find CI with fuzzy matching and suggestions

    Returns:
        {
            "exact_match": ci_data or None,
            "suggestions": [list of similar CIs],
            "confidence": float
        }
    """
    results = search_cmdb(query)

    if not results:
        # Try fuzzy search
        fuzzy_results = search_cmdb(query[:3])  # Partial match
        return {
            "exact_match": None,
            "suggestions": fuzzy_results[:5],
            "confidence": 0.0
        }

    # Check for exact or close match
    for result in results:
        if result['name'].lower() == query.lower():
            return {
                "exact_match": result,
                "suggestions": [],
                "confidence": 1.0
            }

    # Return best matches
    return {
        "exact_match": results[0],  # Best match
        "suggestions": results[1:5],
        "confidence": 0.7
    }
```

## Integration with Other Agents

The SNOW Agent is called by:
- **Supervisor Agent**: To verify CIs before creating firewall rules
- **GitSecOps Agent**: To populate PR metadata with CI information
- **Account Details Agent**: To cross-reference AWS accounts with CIs

## Example Workflow

```
User: "Allow HTTPS to prod-web-01"
  ↓
Supervisor Agent → SNOW Agent: search_configuration_items("prod-web-01")
  ↓
SNOW Agent returns:
{
    "sys_id": "abc123...",
    "name": "prod-web-01.example.com",
    "ip_address": "10.10.5.25",
    "u_aws_account": "123456789012",
    "operational_status": "Operational",
    "support_group": "Platform Team",
    "business_service": "Customer Portal"
}
  ↓
Supervisor Agent → GitSecOps Agent: generate_rule(src_ip="10.10.5.25", ...)
  ↓
GitSecOps Agent → Creates PR with CI metadata in description
```

## Rate Limiting

```python
import time

class ServiceNowRateLimiter:
    """Rate limiter for ServiceNow API calls"""

    def __init__(self, calls_per_minute=60):
        self.calls_per_minute = calls_per_minute
        self.calls = []

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Remove calls older than 1 minute
        self.calls = [call_time for call_time in self.calls
                      if now - call_time < 60]

        if len(self.calls) >= self.calls_per_minute:
            # Wait until oldest call expires
            wait_time = 60 - (now - self.calls[0])
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)

        self.calls.append(now)
```

## Security Considerations

- **Store credentials** in AWS Secrets Manager with automatic rotation
- **Use OAuth 2.0** instead of basic auth (if available)
- **Read-only access** for Phase 2 (CMDB queries only)
- **Write access** required for Phase 3 (CHG creation)
- **TLS 1.2+** for all API calls
- **Audit logging**: Log all ServiceNow API interactions

## Testing

1. **Connection Test**: Verify API authentication and connectivity
2. **CI Search**: Test various search patterns (name, IP, account)
3. **Fuzzy Matching**: Test with typos and partial names
4. **Rate Limiting**: Verify rate limiter prevents API throttling
5. **Error Scenarios**: Test timeout, auth failure, rate limit exceeded
6. **CHG Creation** (Phase 3): Test end-to-end change request workflow

## References

- Jira Tasks: FWAUTO-17, FWAUTO-22
- ServiceNow Table API Documentation
- ServiceNow REST API Reference
- pysnow library: https://pysnow.readthedocs.io/
