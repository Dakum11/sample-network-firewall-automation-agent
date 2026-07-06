To change this agent from GitHub to Azure DevOps, you need to modify two key areas:

## 1. Authentication & API Client

Replace the GitHub PAT with an Azure DevOps Personal Access Token and use the Azure DevOps REST API:

```python
# Configuration
AZURE_DEVOPS_ORG = "your-organization"
AZURE_DEVOPS_PROJECT = "your-project"
REPO_NAME = "your-repo"
REPO_URL = f"https://dev.azure.com/{AZURE_DEVOPS_ORG}/{AZURE_DEVOPS_PROJECT}/_git/{REPO_NAME}"
PAT_TOKEN = "your_azure_devops_pat_token"


# For git operations with authentication
REPO_URL_WITH_AUTH = f"https://{PAT_TOKEN}@dev.azure.com/{AZURE_DEVOPS_ORG}/{AZURE_DEVOPS_PROJECT}/_git/{REPO_NAME}"
```

## 2. Update the Pull Request Function

Replace the create_pull_request function to use Azure DevOps API:

```python
def create_pull_request(branch_name: str, title: str, description: str) -> str:
    """Create a pull request in Azure DevOps"""
    url = f"https://dev.azure.com/{AZURE_DEVOPS_ORG}/{AZURE_DEVOPS_PROJECT}/_apis/git/repositories/{REPO_NAME}/pullrequests?api-version=7.1"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(f':{PAT_TOKEN}'.encode()).decode()}"
    }
    
    data = {
        "sourceRefName": f"refs/heads/{branch_name}",
        "targetRefName": "refs/heads/main",
        "title": title,
        "description": description
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    pr_url = response.json()["url"]
    return f"Pull request created: {pr_url}"
```

## 3. Add Required Import

```python
import base64
```

## Key Differences

• **API Endpoint**: Azure DevOps uses dev.azure.com with organization/project structure
• **Authentication**: Azure DevOps uses Basic auth with base64-encoded PAT (:token format)
• **API Version**: Azure DevOps requires api-version parameter (currently 7.1)
• **Branch References**: Use full ref names like refs/heads/branch-name
• **Repository ID**: Can use repository name directly in the API path

## Getting Azure DevOps PAT

1. Go to Azure DevOps > User Settings > Personal Access Tokens
2. Create new token with "Code (Read & Write)" and "Pull Request Threads (Read & Write)" scopes
3. Copy the token immediately (it won't be shown again)

The rest of the agent (git operations, file tools, model configuration) remains the same since git operations are identical between GitHub and Azure 
DevOps.
