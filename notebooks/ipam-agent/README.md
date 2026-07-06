# Firewall IPAM Agent Development

This folder contains resources for building the Firewall IPAM (IP Address Management) Agent.

## Overview

The IPAM Agent verifies IP address allocations and prevents conflicts:
- Check if IP/CIDR is already allocated
- Verify IP ownership
- Prevent IP conflicts in firewall rules
- Validate IP ranges before rule creation

## Related Jira Tasks

- **FWAUTO-21**: Implement Firewall IPAM Agent (Phase 2/3)

## Getting Started

This folder doesn't have sample notebooks yet. Reference the firewall-logs-tool and account-details-agent for similar integration patterns.

## Key Components to Build

### Tool Definitions

```python
@tool
def check_ip_allocation(ip_or_cidr: str) -> dict:
    """
    Check if an IP or CIDR is allocated and to whom

    Args:
        ip_or_cidr: IP address (192.168.1.1) or CIDR (10.0.0.0/24)

    Returns:
        {
            "allocated": bool,
            "owner": str or None,
            "account_id": str or None,
            "vpc_id": str or None,
            "region": str or None,
            "allocation_date": str or None
        }
    """
```

```python
@tool
def verify_cidr_availability(cidr: str, account_id: str) -> dict:
    """
    Verify if a CIDR range is available for use in firewall rules

    Args:
        cidr: CIDR notation (10.0.0.0/24)
        account_id: AWS account ID

    Returns:
        {
            "available": bool,
            "conflicts": list,
            "suggestions": list  # Alternative ranges if conflicts exist
        }
    """
```

```python
@tool
def get_ip_details(ip_address: str) -> dict:
    """
    Get detailed information about an IP address

    Args:
        ip_address: IP address to look up

    Returns:
        Complete IP allocation details including:
        - Owner, account, VPC, subnet
        - ENI attached to
        - Instance or resource using the IP
        - Public/private designation
    """
```

## IPAM Integration Options

### Option 1: AWS VPC IPAM
If using AWS VPC IPAM service:

```python
import boto3

def initialize_ipam_client(region='ap-southeast-2'):
    """Initialize AWS IPAM client"""
    return boto3.client('ec2', region_name=region)

def query_ipam_pool(cidr: str):
    """Query IPAM pool for CIDR allocation"""
    ec2_client = initialize_ipam_client()

    response = ec2_client.describe_ipam_resource_cidrs(
        Filters=[
            {'Name': 'ipam-resource-cidr', 'Values': [cidr]}
        ]
    )

    return response['IpamResourceCidrs']
```

### Option 2: Custom IPAM Database
If using custom IPAM database (DynamoDB or external system):

```python
def query_ipam_database(ip_or_cidr: str):
    """Query custom IPAM database"""
    # Similar pattern to Account Details Agent
    # Query DynamoDB table with IP allocations
    # Handle cross-account access if needed
```

### Option 3: Network Insights API
Use AWS Network Insights or similar service:

```python
def verify_ip_reachability(ip_address: str, source_cidr: str):
    """Verify IP is reachable from source CIDR"""
    # Use AWS Reachability Analyzer
    # Or custom network analysis
```

## IP Conflict Detection

```python
def check_for_conflicts(new_cidr: str, existing_cidrs: list) -> list:
    """
    Check if new CIDR conflicts with existing allocations

    Args:
        new_cidr: New CIDR to validate
        existing_cidrs: List of existing CIDRs

    Returns:
        List of conflicting CIDRs
    """
    import ipaddress

    new_network = ipaddress.ip_network(new_cidr)
    conflicts = []

    for existing_cidr in existing_cidrs:
        existing_network = ipaddress.ip_network(existing_cidr)

        # Check if networks overlap
        if (new_network.overlaps(existing_network) or
            existing_network.overlaps(new_network)):
            conflicts.append(existing_cidr)

    return conflicts
```

## CIDR Validation

```python
def validate_cidr_syntax(cidr: str) -> dict:
    """
    Validate CIDR notation syntax

    Args:
        cidr: CIDR string to validate

    Returns:
        {
            "valid": bool,
            "network_address": str or None,
            "broadcast_address": str or None,
            "num_addresses": int or None,
            "error": str or None
        }
    """
    import ipaddress

    try:
        network = ipaddress.ip_network(cidr, strict=False)

        return {
            "valid": True,
            "network_address": str(network.network_address),
            "broadcast_address": str(network.broadcast_address),
            "num_addresses": network.num_addresses,
            "netmask": str(network.netmask),
            "is_private": network.is_private,
            "error": None
        }
    except ValueError as e:
        return {
            "valid": False,
            "error": str(e)
        }
```

## Private vs Public IP Detection

```python
def check_ip_type(ip_address: str) -> dict:
    """
    Determine if IP is private, public, reserved, etc.

    Args:
        ip_address: IP address to check

    Returns:
        IP classification and security recommendations
    """
    import ipaddress

    ip = ipaddress.ip_address(ip_address)

    return {
        "ip": str(ip),
        "version": ip.version,  # 4 or 6
        "is_private": ip.is_private,
        "is_global": ip.is_global,
        "is_loopback": ip.is_loopback,
        "is_multicast": ip.is_multicast,
        "is_reserved": ip.is_reserved,
        "security_note": _get_security_note(ip)
    }

def _get_security_note(ip):
    """Get security recommendation based on IP type"""
    if ip.is_private:
        return "Private IP - suitable for internal traffic rules"
    elif ip.is_global:
        return "Public IP - ensure proper justification for external access"
    elif ip.is_loopback:
        return "Loopback IP - generally not used in firewall rules"
    else:
        return "Special use IP - verify intended use"
```

## Integration with Other Agents

The IPAM Agent is called by:
- **GitSecOps Agent**: Verify source/destination IPs before rule creation
- **Account Details Agent**: Cross-reference CIDRs with account allocations
- **Supervisor Agent**: Validate IP inputs in user queries

## Example Workflow

```
User: "Allow traffic from 10.10.5.0/24 to api.example.com"
  ↓
Supervisor Agent → IPAM Agent: verify_cidr_availability("10.10.5.0/24", account_id)
  ↓
IPAM Agent checks:
1. Is CIDR valid syntax? ✓
2. Is it allocated to the correct account? ✓
3. Any overlapping allocations? ✗ Found conflict with 10.10.0.0/16
  ↓
IPAM Agent returns:
{
    "available": False,
    "conflicts": ["10.10.0.0/16 allocated to RT-Prod-DR"],
    "suggestions": ["Use more specific range: 10.10.5.0/25"],
    "recommendation": "CIDR overlaps with existing allocation - refine range"
}
  ↓
Supervisor Agent → Clarify with user or suggest alternative
```

## Caching Strategy

```python
# Cache IP allocation data for 10 minutes
# IPs change less frequently than other data
IP_CACHE_TTL = timedelta(minutes=10)
```

## Performance Optimization

- **Batch Queries**: Query multiple IPs in a single request
- **CIDR Aggregation**: Pre-aggregate large CIDR blocks
- **Index by Account**: Create GSI for faster account-based lookups
- **Cache Negative Results**: Cache "IP not found" results to reduce queries

## Error Handling

```python
def safe_ip_lookup(ip_or_cidr: str) -> dict:
    """
    Safe IP lookup with graceful error handling

    Returns error-friendly responses for invalid inputs
    """
    try:
        # Validate syntax first
        validation = validate_cidr_syntax(ip_or_cidr)
        if not validation['valid']:
            return {
                "error": "Invalid IP/CIDR format",
                "details": validation['error'],
                "suggestion": "Check IP address format (e.g., 192.168.1.1 or 10.0.0.0/24)"
            }

        # Proceed with lookup
        return check_ip_allocation(ip_or_cidr)

    except Exception as e:
        logger.error(f"IPAM lookup failed: {str(e)}")
        return {
            "error": "IPAM service unavailable",
            "details": str(e),
            "fallback": "Proceeding without IP verification - manual review required"
        }
```

## Security Considerations

- **Validate all IP inputs**: Prevent injection attacks
- **Read-only access**: IPAM agent should not allocate/deallocate IPs
- **Audit logging**: Log all IP verifications for security audit
- **Private IP warnings**: Flag rules allowing access to private IPs from public sources

## Testing

1. **Syntax Validation**: Test various CIDR formats (valid and invalid)
2. **Conflict Detection**: Test overlapping CIDR ranges
3. **IP Type Detection**: Test private, public, reserved IPs
4. **Performance**: Test with large CIDR lists
5. **Error Scenarios**: Test IPAM service unavailable

## References

- Jira Task: FWAUTO-21
- AWS VPC IPAM Documentation
- Python ipaddress module: https://docs.python.org/3/library/ipaddress.html
- RFC 1918 (Private Address Space)
- RFC 6890 (Special-Purpose IP Address Registries)
