"""
Improved OpenSearch tools for querying AWS Network Firewall logs
Following Strands SDK best practices with enhanced error handling and documentation
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import boto3
import boto3.dynamodb.conditions
from aws_requests_auth.aws_auth import AWSRequestsAuth
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from dateutil import parser as date_parser
from opensearchpy import OpenSearch, RequestsHttpConnection
from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
endpoint = "https://vxoxfikba1rth5rwfmvc.ap-southeast-2.aoss.amazonaws.com"
region = "ap-southeast-2"
role_arn = "arn:aws:iam::307987194911:role/XAccount-OpenSearch-Firewall-Logs-Role"

# Global OpenSearch client - initialized after class definition
opensearch_client = None


class OpenSearchClient:
    """
    Enhanced OpenSearch Serverless client for firewall logs with improved error handling
    """

    def __init__(
        self, endpoint: str, region: str = "ap-southeast-2", role_arn: str = None
    ):
        self.endpoint = endpoint
        self.region = region
        self.role_arn = role_arn
        self._client = None
        self._credentials = None
        self._connection_tested = False

    def _assume_role(self):
        """Assume the cross-account IAM role and return credentials"""
        if not self.role_arn:
            # Use default credentials if no role specified
            session = boto3.Session()
            credentials = session.get_credentials()
            if not credentials:
                raise RuntimeError(
                    "No AWS credentials found. Please configure your AWS credentials."
                )
            return credentials

        try:
            # Create STS client to assume role
            sts_client = boto3.client("sts", region_name=self.region)

            # Assume the cross-account role
            response = sts_client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName="FirewallLogAnalysisAgent",
                DurationSeconds=3600,  # 1 hour session
            )

            # Extract credentials
            credentials = response["Credentials"]

            # Create a credentials object
            from botocore.credentials import Credentials

            return Credentials(
                access_key=credentials["AccessKeyId"],
                secret_key=credentials["SecretAccessKey"],
                token=credentials["SessionToken"],
            )

        except Exception as e:
            logger.error(f"Failed to assume role {self.role_arn}: {str(e)}")
            raise RuntimeError(
                f"Role assumption failed: {str(e)}. Please check your IAM permissions."
            ) from e

    @property
    def client(self):
        """Lazy initialization of OpenSearch client with enhanced error handling"""
        if self._client is None:
            try:
                # Get credentials (either assumed role or default)
                credentials = self._assume_role()

                # Extract host from endpoint
                host = self.endpoint.replace("https://", "").replace("http://", "")

                # Create AWS auth for OpenSearch Serverless
                awsauth = AWSRequestsAuth(
                    aws_access_key=credentials.access_key,
                    aws_secret_access_key=credentials.secret_key,
                    aws_token=credentials.token,
                    aws_host=host,
                    aws_region=self.region,
                    aws_service="aoss",  # OpenSearch Serverless
                )

                self._client = OpenSearch(
                    hosts=[{"host": host, "port": 443}],
                    http_auth=awsauth,
                    use_ssl=True,
                    verify_certs=True,
                    connection_class=RequestsHttpConnection,
                    timeout=30,  # Increased timeout for better reliability
                    max_retries=2,  # Allow retries
                    retry_on_timeout=True,
                    http_compress=False,
                )

                logger.debug(f"OpenSearch client initialized for host: {host}")

            except Exception as e:
                logger.error(f"Failed to initialize OpenSearch client: {str(e)}")
                raise RuntimeError(
                    f"OpenSearch client initialization failed: {str(e)}"
                ) from e

        return self._client

    def test_connection(self) -> Dict[str, Any]:
        """Test the OpenSearch connection with detailed diagnostics"""
        try:
            # Test basic connectivity
            response = self.client.search(
                index="alert-logs-*",
                body={
                    "size": 0,
                    "query": {"range": {"event.timestamp": {"gte": "now-1m"}}},
                },
                timeout=10,
            )

            total_docs = response.get("hits", {}).get("total", {}).get("value", 0)
            self._connection_tested = True

            return {
                "status": "success",
                "total_documents": total_docs,
                "connection_time": datetime.utcnow().isoformat(),
                "endpoint": self.endpoint,
                "region": self.region,
                "role_arn": self.role_arn,
            }

        except Exception as e:
            logger.error(f"OpenSearch connection test failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "endpoint": self.endpoint,
                "region": self.region,
                "suggestions": [
                    "Check network connectivity to OpenSearch endpoint",
                    "Verify AWS credentials and permissions",
                    "Ensure OpenSearch collection access policies allow your IAM identity",
                    "Check if the specified role ARN exists and is assumable",
                ],
            }


def initialize_opensearch(endpoint, region, role_arn):
    """Initialize the global OpenSearch client with hardcoded values"""
    global opensearch_client

    try:
        opensearch_client = OpenSearchClient(endpoint, region, role_arn)
        logger.debug("OpenSearch client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenSearch client: {str(e)}")
        # Don't raise here to allow module import to succeed


# Initialize on module import
initialize_opensearch(endpoint, region, role_arn)


@tool
def test_opensearch_connection() -> Dict[str, Any]:
    """
    Test the OpenSearch connection and role assumption with detailed diagnostics.

    This tool verifies that the OpenSearch Serverless connection is working properly,
    including authentication, network connectivity, and basic search functionality.

    Returns:
        Dictionary containing connection test results with status, diagnostics,
        and suggestions for troubleshooting if connection fails.

    Raises:
        RuntimeError: If OpenSearch client is not initialized
    """
    if not opensearch_client:
        raise RuntimeError(
            "OpenSearch client not initialized. Please check the module initialization."
        )

    logger.debug("Testing OpenSearch connection...")
    return opensearch_client.test_connection()


@tool
def search_firewall_logs(
    query: str,
    time_range_hours: int = 1,
    max_results: int = 100,
    account_filter: Optional[str] = None,
    action_filter: Optional[str] = None,
    index_pattern: str = "alert-logs-*",
) -> Dict[str, Any]:
    """
    Search AWS Network Firewall logs in OpenSearch Serverless with advanced filtering.

    This tool searches through firewall logs with flexible filtering options and natural
    language query support. It provides comprehensive log analysis capabilities for
    security monitoring and traffic pattern analysis.

    Args:
        query: Natural language query or specific search terms. Can include IP addresses,
               domain names, account IDs, or security-related keywords.
        time_range_hours: Number of hours to look back from current time (default: 1).
                         Use larger values for trend analysis.
        max_results: Maximum number of results to return (default: 100, max: 1000).
        account_filter: Filter by specific AWS account ID. Can be account number or
                       account alias (e.g., "123456789012" or "RTCORP").
        action_filter: Filter by action type:
                      - 'blocked' or 'dropped': Show only blocked/dropped traffic
                      - 'allowed' or 'passed': Show only allowed traffic
        index_pattern: OpenSearch index pattern to search (default: "alert-logs-*").

    Returns:
        Dictionary containing search results with metadata:
        - total_hits: Total number of matching documents
        - returned_results: Number of results in this response
        - time_range_hours: Time range searched
        - query_time: When the query was executed
        - results: Array of log entries with parsed fields including:
          - timestamp, firewall_name, src_ip, dest_ip, ports, protocol
          - src_account, dest_account, action, verdict, signature
          - sni (domain name), app_proto, availability_zone

    Raises:
        RuntimeError: If OpenSearch client is not initialized
        Exception: If search query fails due to syntax errors or connectivity issues
    """
    if not opensearch_client:
        raise RuntimeError(
            "OpenSearch client not initialized. Please check your AWS credentials and permissions."
        )

    # Validate parameters
    if time_range_hours <= 0:
        raise ValueError("time_range_hours must be positive")

    if max_results <= 0 or max_results > 1000:
        raise ValueError("max_results must be between 1 and 1000")

    if action_filter and action_filter.lower() not in [
        "blocked",
        "dropped",
        "allowed",
        "passed",
    ]:
        raise ValueError(
            "action_filter must be one of: 'blocked', 'dropped', 'allowed', 'passed'"
        )

    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_range_hours)

        logger.debug(f"Searching firewall logs from {start_time} to {end_time}")

        # Build the OpenSearch query
        search_body = {
            "size": max_results,
            "sort": [{"event.timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {
                            "range": {
                                "event.timestamp": {
                                    "gte": start_time.isoformat(),
                                    "lte": end_time.isoformat(),
                                }
                            }
                        }
                    ],
                }
            },
        }

        # Add text search if query provided
        if query and query.strip():
            search_body["query"]["bool"]["must"].append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "event.tls.sni^3",  # Higher weight for domain names
                            "event.src_account^2",
                            "event.dest_account^2",
                            "event.alert.signature^2",
                            "event.src_ip",
                            "event.dest_ip",
                            "firewall_name",
                            "event.proto",
                            "event.app_proto",
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO",  # Allow fuzzy matching
                    }
                }
            )

        # Add account filter
        if account_filter:
            search_body["query"]["bool"]["filter"].append(
                {
                    "bool": {
                        "should": [
                            {"term": {"event.src_account.keyword": account_filter}},
                            {"term": {"event.dest_account.keyword": account_filter}},
                        ]
                    }
                }
            )

        # Add action filter with improved logic
        if action_filter:
            action_lower = action_filter.lower()
            if action_lower in ["blocked", "dropped"]:
                search_body["query"]["bool"]["filter"].extend(
                    [
                        {"terms": {"event.alert.action.keyword": ["blocked"]}},
                        {"terms": {"event.verdict.action.keyword": ["drop"]}},
                    ]
                )
            elif action_lower in ["allowed", "passed"]:
                search_body["query"]["bool"]["filter"].extend(
                    [
                        {"terms": {"event.alert.action.keyword": ["allowed"]}},
                        {"terms": {"event.verdict.action.keyword": ["pass"]}},
                    ]
                )

        # Execute search with timeout
        logger.debug(f"Executing OpenSearch query: {json.dumps(search_body, indent=2)}")

        response = opensearch_client.client.search(
            index=index_pattern, body=search_body, timeout=30
        )

        # Process results
        hits = response.get("hits", {})
        total_hits = hits.get("total", {}).get("value", 0)
        results = []

        for hit in hits.get("hits", []):
            source = hit.get("_source", {})
            event = source.get("event", {})

            # Extract and structure key information
            result = {
                "timestamp": event.get("timestamp"),
                "firewall_name": source.get("firewall_name"),
                "availability_zone": source.get("availability_zone"),
                "src_ip": event.get("src_ip"),
                "dest_ip": event.get("dest_ip"),
                "src_port": event.get("src_port"),
                "dest_port": event.get("dest_port"),
                "protocol": event.get("proto"),
                "app_protocol": event.get("app_proto"),
                "src_account": event.get("src_account"),
                "dest_account": event.get("dest_account"),
                "action": event.get("alert", {}).get("action"),
                "verdict": event.get("verdict", {}).get("action"),
                "signature": event.get("alert", {}).get("signature"),
                "severity": event.get("alert", {}).get("severity"),
                "sni": event.get("tls", {}).get("sni"),
                "score": hit.get("_score"),  # Relevance score
            }
            results.append(result)

        logger.debug(
            f"Search completed: {len(results)} results returned out of {total_hits} total hits"
        )

        return {
            "total_hits": total_hits,
            "returned_results": len(results),
            "time_range_hours": time_range_hours,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "query_time": datetime.utcnow().isoformat(),
            "query": query,
            "filters": {
                "account_filter": account_filter,
                "action_filter": action_filter,
                "index_pattern": index_pattern,
            },
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error searching firewall logs: {str(e)}")
        raise Exception(
            f"Firewall log search failed: {str(e)}. Please check your query syntax and try again."
        ) from e


model_id = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[
        search_firewall_logs,
    ],
    system_prompt="""You are an AWS Network Firewall Log Analysis Assistant. You help users analyze AWS Network Firewall traffic alert logs stored in OpenSearch Serverless.

Your capabilities include:
- Searching firewall logs with flexible queries and natural language understanding

Key information about the log structure:
- Logs contain both allowed and blocked traffic events from AWS Network Firewall
- Each log entry includes source/destination IPs, ports, protocols, and AWS account information
- The src_account, src_vpc, and src_region fields are injected during log processing
- Traffic can be filtered by action (allowed/blocked/dropped), account, time range, ports, and protocols
- SNI (Server Name Indication) field contains destination URLs/domains for TLS traffic
- Default time range is 1 hour unless specified otherwise
- Logs are indexed in OpenSearch Serverless with pattern "alert-logs-*"

IMPORTANT - Understanding No Results:
- If NO logs are found, this means traffic either:
  1. Has not been initiated/attempted yet from that source
  2. Was blocked at the Security Group level (before reaching the firewall, so no firewall log is generated)
  3. Falls outside the specified time range
- AWS Network Firewall only logs traffic that reaches it - Security Groups filter traffic before it reaches the firewall

When answering questions:
1. Provide a direct, concise answer to what was asked
2. Include relevant statistics (total hits, time range, key findings)
3. Highlight critical security findings if present (blocked traffic, suspicious patterns)
4. Do NOT provide recommendations, solutions, or suggestions unless specifically requested
5. Do NOT provide follow-up query suggestions unless asked
6. Keep responses factual and brief

IMPORTANT: Answer ONLY what was asked. Do not elaborate with security recommendations, best practices, or suggested actions unless explicitly requested by the user.

The OpenSearch endpoint is pre-configured and ready to use. Be accurate and concise.""",
)


@tool
async def firewall_logs_agent(prompt):
    """
    Search AWS Network Firewall logs in OpenSearch Serverless with advanced filtering.

    Args:
        prompt: Detailed description of the firewall log analysis query

    Yields:
        Streamed analysis results from the agent with tool usage events
    """
    if not prompt.strip():
        yield "Error: Prompt cannot be blank"
        return

    user_input = prompt
    agent_stream = agent.stream_async(user_input)
    tool_name = None
    try:
        async for event in agent_stream:
            # Handle streaming events from nested tools
            if tool_stream := event.get("tool_stream_event"):
                if update := tool_stream.get("data"):
                    yield f"\n  ↳ {update}\n"

            # Handle tool usage events
            elif (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                yield f"\n\n  ↳ 🔧 **Firewall Logs tool: {tool_name}**\n\n"

            # Handle data/text events
            elif "data" in event:
                tool_name = None
                yield event["data"]
    except Exception as e:
        yield f"\n\nError in Firewall Logs agent: {str(e)}\n"


if __name__ == "__main__":
    app.run()
