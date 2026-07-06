# Firewall Logs Tool Development

This folder contains resources for building the Firewall Logs Tool that queries OpenSearch.

## Overview

The Firewall Logs Tool enables agents to:
- Translate natural language to OpenSearch queries
- Query firewall logs from OpenSearch Serverless
- Parse and summarize results
- Identify patterns and anomalies

## Related Jira Tasks

- **FWAUTO-13**: Firewall logs tool implemented (Phase 1)

## Available Resources

### network_firewall_analyser_agent.py
**Complete example implementation** using Strands SDK! This file demonstrates:

- **OpenSearch Integration**: Cross-account role assumption and connection management
- **Tool Definitions**: Multiple tools using `@tool` decorator:
  - `test_opensearch_connection()` - Verify connectivity
  - `search_firewall_logs()` - Flexible log searching with filters
  - `get_blocked_traffic_by_account()` - Security-focused analysis
  - `get_top_urls_by_account()` - Traffic pattern analysis
  - `get_traffic_summary_by_account()` - Comprehensive summaries
- **Agent Implementation**: Full `FirewallAnalyzerAgent` class with:
  - Streaming async support
  - Activity notifications
  - Conversation history management
  - Error handling

## Getting Started

1. **Study the example code** in `network_firewall_analyser_agent.py`
2. Understand the OpenSearch query patterns used
3. Review the tool definitions and how they're integrated
4. Consider how to adapt this for AgentCore Runtime deployment

## Key Patterns in the Example

### Cross-Account Access
```python
# Assumes a role in the OpenSearch account
def _assume_role(self):
    sts_client = boto3.client("sts", region_name=self.region)
    response = sts_client.assume_role(
        RoleArn=self.role_arn,
        RoleSessionName="FirewallLogAnalysisAgent"
    )
```

### Tool Definition with Strands
```python
@tool
def search_firewall_logs(query: str, time_range_hours: int = 1, ...):
    """
    Comprehensive docstring used by LLM to understand tool capability
    """
    # Implementation
```

### OpenSearch Query Building
```python
search_body = {
    "query": {
        "bool": {
            "must": [...],
            "filter": [...]
        }
    }
}
```

## Adapting for Your Implementation

Consider these approaches:

### Option 1: Use MCP Server
Instead of implementing OpenSearch client directly, use an MCP Server for OpenSearch:
- Simpler integration
- Standardized interface
- Less boilerplate code

### Option 2: Adapt the Example
Take the existing code and modify for AgentCore:
- Replace Strands SDK with AgentCore tool definitions
- Keep the OpenSearch query logic (it's solid!)
- Maintain the cross-account access pattern

### Option 3: Natural Language Query Translation
Let the LLM generate OpenSearch DSL:
- Provide schema documentation to the LLM
- Let it construct queries dynamically
- More flexible but requires careful prompt engineering

## Implementation Tips

- **Caching**: The example doesn't implement caching - you should add this (5-minute TTL)
- **Default Time Ranges**: The example defaults to 1 hour - consider user experience
- **Error Messages**: The example has good error handling - keep this pattern
- **Security Analysis**: Notice how the example highlights blocked traffic - very useful!
- **Aggregations**: The summary functions show powerful OpenSearch aggregation patterns

## Testing

Before deploying:
1. Test OpenSearch connectivity and role assumption
2. Verify queries work with your log structure
3. Test with various time ranges and account IDs
4. Confirm performance with large result sets
5. Test error scenarios (connection failures, timeouts)

## References

- Jira Task: FWAUTO-13
- OpenSearch Query DSL Documentation
- AWS SigV4 Authentication
- Strands SDK Documentation (for understanding the example)
