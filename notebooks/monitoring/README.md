# Monitoring and Observability

This folder contains resources for implementing monitoring and observability for the Firewall Automation Chatbot.

## Overview

Comprehensive monitoring using:
- AWS Bedrock AgentCore Monitoring
- CloudWatch Logs and Metrics
- AWS X-Ray for distributed tracing
- Third-party observability platforms

## Related Jira Tasks

- **FWAUTO-20**: Implement monitoring and observability (Phase 1)

## Available Notebooks

### observability-with-braintrust.ipynb
Integration with Braintrust for:
- Agent performance tracking
- Evaluation and testing
- Metrics visualization

### observability-with-langfuse.ipynb
Integration with Langfuse for:
- Trace analysis
- Agent debugging
- Performance monitoring

## Getting Started

1. Review both observability notebooks to understand integration patterns
2. Decide on observability tools (CloudWatch + third-party)
3. Plan your metrics: agent invocations, success rate, latency, errors
4. Design dashboards for different audiences (engineers, operations, stakeholders)

## Key Metrics to Track

### Agent Metrics
- Invocation count and success rate
- Response time (average, P95, P99)
- Error rate by agent type
- Tool usage statistics

### Integration Health
- OpenSearch query latency
- DynamoDB access patterns
- ServiceNow API availability
- Azure DevOps API response times

### Business Metrics
- Active users
- Firewall rules created
- Pull requests submitted
- User satisfaction scores

## References

- Jira Task: FWAUTO-20
- AWS CloudWatch and X-Ray Documentation
