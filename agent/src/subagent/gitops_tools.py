"""
GitOps tools for repository management and pull request creation
"""

import base64
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import boto3
import requests
from strands.tools import tool

# Load configuration from environment variables (no defaults - must be set)
AZURE_DEVOPS_ORG = os.getenv("AZURE_DEVOPS_ORG")
AZURE_DEVOPS_PROJECT = os.getenv("AZURE_DEVOPS_PROJECT")
REPO_NAME = os.getenv("REPO_NAME")
VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"

# Warn if git config is missing — agent can still serve other tools
_missing_vars = []
if not AZURE_DEVOPS_ORG:
    _missing_vars.append("AZURE_DEVOPS_ORG")
if not AZURE_DEVOPS_PROJECT:
    _missing_vars.append("AZURE_DEVOPS_PROJECT")
if not REPO_NAME:
    _missing_vars.append("REPO_NAME")
if _missing_vars:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        f"GitOps tools will be unavailable — missing env vars: {', '.join(_missing_vars)}. "
        "Git clone, commit, and PR operations will fail until these are configured."
    )


def get_secret(secret_name: str) -> str:
    client = boto3.client("secretsmanager", region_name=os.getenv('AWS_REGION', 'us-east-1'))
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]


def get_repo_url() -> tuple[str, str]:
    response = json.loads(get_secret("firewall-chatbot/azure-devops/pat"))
    username = response["username"]
    pat_token = response["password"]

    return username, pat_token


def run_subprocess(command, cwd=None):
    """Run a subprocess command and handle output."""
    if VERBOSE:
        print(f"Running command: {' '.join(command)} in {cwd or os.getcwd()}")
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=VERBOSE,
        text=True,
    )
    if VERBOSE:
        print("Command return code:", result.returncode)
        print("Stdout:", result.stdout)
        print("Stderr:", result.stderr)


@tool
def clone_repo(business_unit: str, project_name: str, target: str) -> str:
    """
    Clone the firewall automation repository and create a new branch for changes.

    Use this tool when starting any firewall rule modification workflow. This is always
    the first step before making configuration changes, as it sets up the working
    environment with proper version control.

    This tool clones the firewall automation repository from Azure DevOps,
    creates a new feature branch following naming conventions, and validates the
    repository structure to ensure successful setup.

    Example response for successful clone:
        "Repository cloned successfully!

        Repository Path: /tmp/tmpxyz123/network-firewall
        Branch Name: ACME-WebApp-Prod-161225

        You can now make changes to files in this repository.
        Use these values when calling commit_and_push later."

    Notes:
        - Provide the business unit, project_name, and target to the function, and this tool will construct the branch name
        - Use hyphens (-) to separate words. Spaces are not supported by git.
        - Avoid special characters in any of the inputs
        - Branch names will follow format: <Business Unit>-<Project>-<Target>-<DDMMYY>
        - Date format (DDMMYY) is automatically calculated from current date when tool runs
        - Repository is cloned to a temporary directory for isolation
        - Creates a new branch immediately to avoid conflicts with main branch

    Args:
        business_unit: Business unit or department name
                    Examples: "ACME", "OPS", "HR"
        project_name: Project name for the firewall change, provided by the user
        target: The name of the target that will be whitelisted with this change

    Returns:
        String containing structured information with clearly labeled fields:
        - Repository Path: Absolute path to the cloned repository
        - Branch Name: The constructed branch name with date

        This structured format makes it easy to extract values for subsequent tool calls.
    """
    try:
        # Calculate current date in DDMMYY format
        current_date = datetime.now().strftime("%d%m%y")

        # Construct branch name
        branch_name = f"{business_unit}-{project_name}-{target}-{current_date}"

        # Create temporary directory for repository
        temp_dir = tempfile.mkdtemp()
        repo_path = Path(temp_dir) / "network-firewall"

        # Fetch PAT token
        _, pat_token = get_repo_url()
        repo_url = f"https://{pat_token}@{AZURE_DEVOPS_ORG}.visualstudio.com/{AZURE_DEVOPS_PROJECT}/_git/{REPO_NAME}"

        # Clone repository and create new branch
        run_subprocess(["git", "clone", repo_url, str(repo_path)])
        run_subprocess(["git", "checkout", "-b", branch_name], cwd=repo_path)

        return f"""Repository cloned successfully!

Repository Path: {repo_path}
Branch Name: {branch_name}

You can now make changes to files in this repository.
Use these values when calling commit_and_push later."""
    except Exception as e:
        return f"Error in repository cloning: {str(e)}"


@tool
def commit_and_push(repo_path: str, branch_name: str, commit_message: str) -> str:
    """
    Commit changes and push to remote branch after user confirmation.

    Use this tool only after the user has explicitly confirmed the proposed changes.
    This tool stages all modifications, creates a commit with a descriptive message,
    and pushes the changes to the remote Azure DevOps repository.

    This tool handles the Git workflow for firewall configuration changes, ensuring
    all modifications are properly versioned and available for pull request creation.
    It performs atomic operations to maintain repository integrity.

    Example response for successful commit:
        "Changes committed and pushed to branch ACME-WebApp-Prod-{current_date}
        ✅ Git operations completed:
        - 3 files staged for commit
        - Commit created with message: 'Add firewall rules for web application access'
        - Changes pushed to remote origin successfully"

    Notes:
        - Only call this tool after user has confirmed the changes to be made
        - All modified files in the repository are automatically staged
        - Commit messages should clearly describe the firewall changes made
        - Push operation makes changes available for pull request creation
        - Requires valid Git credentials and repository access

    Args:
        repo_path: Absolute path to the cloned repository directory
                  Example: "/tmp/tmpxyz123/network-firewall"
        branch_name: Name of the feature branch to commit to
                    Format: <Business Unit>-<Project>-<Target>-<DDMMYY>
        commit_message: Descriptive message explaining the firewall changes
                       Examples: "Add HTTPS access rules for production web servers",
                                "Remove deprecated FTP rules from legacy systems"

    Returns:
        String confirmation of successful commit and push operations.
        Includes details about files staged, commit creation, and push status.
    """
    try:
        # Stage all changes
        run_subprocess(["git", "add", "."], cwd=repo_path)

        # Commit with message
        run_subprocess(["git", "commit", "-m", commit_message], cwd=repo_path)

        # Push to remote branch
        run_subprocess(["git", "push", "origin", branch_name], cwd=repo_path)

        return f"Changes committed and pushed to branch {branch_name}"
    except Exception as e:
        return f"Error in commit and push: {str(e)}"


@tool
def format_pr_description(
    requestor_name: str,
    requestor_email: str,
    project_name: str,
    business_unit: str,
    sra_number: str,
    business_need: str,
    aws_account_name: str,
    aws_account_number: str,
    vpc_id: str,
    network_objects: str,
    firewall_rules: str,
    repo_path: str,
    change_request_id: str = None,
    change_url: str = None,
) -> str:
    """
    Format a pull request description by reading and populating the official PR template.

    Use this tool to create standardized PR descriptions that comply with organizational
    change management requirements. This tool MUST first read the PR template file from
    the repository before formatting the description.

    This tool performs these steps in order:
    1. Read the PR template from .azuredevops/pull_request_template/branches/main.md
    2. Parse the template structure and identify all required fields
    3. Populate each section with the provided information
    4. Mark all checklist items as completed (change [ ] to [x])
    5. **DISPLAY the complete formatted PR description to the user**
    6. **ASK for user confirmation and approval**
    7. **ITERATE and make changes if user requests modifications**
    8. **Only return final result after user confirms they are satisfied**

    Notes:
        - ALWAYS read the template file first using the file_read tool
        - ALWAYS display the complete formatted result to the user before finishing
        - ALWAYS wait for user confirmation before considering task complete
        - Make modifications based on user feedback and show updated version
        - Template contains exact format requirements for all sections
        - All checklist boxes must be marked as completed: - [x]

    Args:
        requestor_name: Full name of the person requesting the firewall change
        requestor_email: Email address of the requestor
        project_name: Name of the project requiring firewall changes
        business_unit: Business unit or department name
        sra_number: Security Risk Assessment number
        business_need: Business justification for the firewall changes
        aws_account_name: Descriptive name of the target AWS account
        aws_account_number: 12-digit AWS account number
        vpc_id: VPC identifier where changes will be applied
        network_objects: Table data for network objects (object_name, ip_address:port, description)
        firewall_rules: Table data for rules (ADD/REMOVE/MODIFY, source, destination, port, protocol, PERMIT/DENY)
        repo_path: Path to repository containing the PR template file
        change_request_id: ServiceNow change request ID (optional)
        change_url: Direct URL to the change request (optional)

    Returns:
        Complete formatted PR description that has been reviewed and approved by the user.
        Only returns after user explicitly confirms satisfaction with the result.
    """
    try:
        # Read the PR template - MUST exist, no fallback
        template_path = (
            f"{repo_path}/.azuredevops/pull_request_template/branches/main.md"
        )

        with open(template_path, "r") as f:
            template_content = f.read()

        # Replace General Information section
        template_content = template_content.replace(
            "- Requestor Name:", f"- Requestor Name: {requestor_name}"
        )
        template_content = template_content.replace(
            "- Requestor Email:", f"- Requestor Email: {requestor_email}"
        )
        template_content = template_content.replace(
            "- Name of Project:", f"- Name of Project: {project_name}"
        )
        template_content = template_content.replace(
            "- Business Unit:", f"- Business Unit: {business_unit}"
        )
        template_content = template_content.replace(
            "- SRA Number:", f"- SRA Number: {sra_number}"
        )

        # Replace Business Need section
        template_content = template_content.replace(
            "Tell us your business need for the change. What are you trying to accomplish?",
            business_need,
        )

        # Replace AWS Account Information table - remove example row and add actual data
        template_content = template_content.replace(
            "| (EXAMPLE) Example-Account | 012345678910 | vpc-abcdefg123 |",
            f"| {aws_account_name} | {aws_account_number} | {vpc_id} |",
        )

        # Replace Network Objects table - remove example rows and add actual data
        network_objects_section = re.search(
            r"(## Network Objects.*?\n\|.*?\n\|.*?\n)((?:\|.*?\n)+)",
            template_content,
            re.DOTALL,
        )
        if network_objects_section:
            template_content = template_content.replace(
                network_objects_section.group(2), network_objects + "\n"
            )

        # Replace Address Request Details table - remove example row and add actual data
        address_section = re.search(
            r"(## Address Request Details.*?\n\|.*?\n\|.*?\n)((?:\|.*?\n)+)",
            template_content,
            re.DOTALL,
        )
        if address_section:
            template_content = template_content.replace(
                address_section.group(2), firewall_rules + "\n"
            )

        # Mark all checklist items as completed
        formatted_description = template_content.replace("- [ ]", "- [x]")

        # Add change request link to the top if provided
        if change_request_id and change_url:
            cr_header = f"**Change Request:** [{change_request_id}]({change_url})\n\n"
            formatted_description = cr_header + formatted_description
        elif change_request_id:
            cr_header = f"**Change Request ID:** {change_request_id}\n\n"
            formatted_description = cr_header + formatted_description

        # Display the formatted description to the user
        print("\n" + "=" * 80)
        print("FORMATTED PR DESCRIPTION:")
        print("=" * 80)
        print(formatted_description)
        print("=" * 80)

        return f"""Here is the formatted PR description:
{formatted_description}

Please review the above PR description. Does this look correct? Would you like me to make any changes before creating the pull request?"""
    except Exception as e:
        return f"Error formatting PR description: {str(e)}"


@tool
def create_pull_request(branch_name: str, title: str, description: str) -> str:
    """
    Create a pull request using Azure DevOps API after user confirmation.

    Use this tool ONLY after the user has explicitly confirmed the PR title and
    description are correct. This tool creates the actual pull request in Azure DevOps
    and cannot be undone, so user approval is mandatory.

    This tool integrates with Azure DevOps REST API to create pull requests from
    feature branches to the main branch, enabling the standard code review and
    approval workflow for firewall configuration changes.

    Example response for successful PR creation:
        "Pull request created: https://dev.azure.com/ACME/MyProject/_git/MyRepo/pullrequest/123
        ✅ PR Details:
        - Title: [CHG0012345] - Add HTTPS access for production web servers
        - Source: ACME-WebApp-Prod-{current_date}
        - Target: main
        - Status: Active and ready for review"

    Notes:
        - ONLY call this tool after user confirms PR title and description
        - Creates PR from feature branch to main branch automatically
        - Uses Azure DevOps PAT token for authentication
        - PR title should include change request ID when available: [CHG12345] - Description
        - Once created, PR enters standard review and approval workflow
        - Cannot be undone - PR creation is permanent

    Args:
        branch_name: Source branch name containing the firewall changes
                    Format: <Business Unit>-<Project>-<Target>-<DDMMYY>
        title: PR title following format requirements
              With CR: "[CHG0012345] - Add HTTPS access for web servers"
              Without CR: "Add HTTPS access for web servers"
        description: Complete formatted PR description that user has approved
                    Must include all required sections and completed checklists

    Returns:
        String containing the PR URL and confirmation details.
        Includes direct link to the created pull request for immediate access.
    """
    try:
        # Retrieve PAT for authentication
        username, pat_token = get_repo_url()

        url = f"https://{AZURE_DEVOPS_ORG}.visualstudio.com/{AZURE_DEVOPS_PROJECT}/_apis/git/repositories/{REPO_NAME}/pullrequests?api-version=7.1"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {base64.b64encode(f'{username}:{pat_token}'.encode()).decode()}",
        }

        data = {
            "sourceRefName": f"refs/heads/{branch_name}",
            "targetRefName": "refs/heads/main",
            "title": title,
            "description": description,
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        pr_data = response.json()
        pr_id = pr_data["pullRequestId"]

        # Construct the web UI URL instead of using the API URL
        web_pr_url = f"https://{AZURE_DEVOPS_ORG}.visualstudio.com/{AZURE_DEVOPS_PROJECT}/_git/{REPO_NAME}/pullrequest/{pr_id}"

        return f"Pull request created: {web_pr_url}"
    except Exception as e:
        return f"Error creating pull request: {str(e)}"
