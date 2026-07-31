# AgentCore Identity Integration

This folder contains resources for implementing identity and authentication with AgentCore.

## Overview

AgentCore Identity enables:
- Integration with Azure AD (Entra ID) for SSO
- User context passing to agents
- Role-based access control
- Secure authentication flows

## Related Jira Tasks

- **FWAUTO-25**: AgentCore Identity (Phase 2)

## Available Notebooks

### identity-setup.ipynb
Guide to setting up identity integration including:
- Azure AD integration patterns
- User attribute mapping
- Authentication flow configuration
- Testing identity setup

## Getting Started

1. Review **identity-setup.ipynb** to understand identity concepts
2. Understand existing Azure AD setup (FWAUTO-7 - already completed)
3. Design how user context flows from Web App → ALB → Cognito → AgentCore
4. Implement user scoping for memory and access control

## Key Considerations

- User identity propagation through the stack
- How to scope memory by user
- Role-based access (who can create rules? who can view logs?)
- Audit logging requirements
- Session management and token refresh

## Integration Points

- **ALB**: Authenticates users via Cognito (Azure AD federation)
- **Web App**: Receives user info from ALB headers
- **AgentCore**: Receives user context for personalization
- **Memory**: Scoped to user sessions

## References

- Jira Task: FWAUTO-25
- Related: FWAUTO-7 (Azure Enterprise application - completed)
- AWS Cognito and AgentCore Identity Documentation
