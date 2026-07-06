"""
title: Firewall Log Analyzer Agent Function
author: Marcus Rosen
author_url: https://github.com/aws-samples/aws-network-firewall-automation-agent
version: 0.1
description: Integration with Strands Agent SDK with OpenWeb UI
This module defines a Pipe class that utilizes Strands SDK with to query OpenSearch containing firewall logs and generate a response.
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, validator

# Set log level to info
logging.getLogger().setLevel(level=logging.INFO)
logger = logging.getLogger()


################## STRANDS AGENT CODE ##################

"""
Improved AWS Network Firewall Log Analysis Agent
Following Strands SDK best practices and recommendations
"""
import logging
from typing import Any, Dict, Optional

from strands import Agent
from strands_tools import calculator, current_time

logger = logging.getLogger(__name__)

# Enhanced system prompt with clearer instructions
SYSTEM_PROMPT = """You are an AWS Network Firewall Log Analysis Assistant. You help users analyze AWS Network Firewall traffic alert logs stored in OpenSearch Serverless.

Your capabilities include:
- Searching firewall logs with flexible queries and natural language understanding
- Finding blocked traffic by AWS account with detailed analysis
- Identifying top URLs/domains accessed by accounts with security insights
- Providing comprehensive traffic summaries and statistics
- Analyzing traffic patterns and identifying potential security events
- Performing time-based analysis and trend identification

Key information about the log structure:
- Logs contain both allowed and blocked traffic events from AWS Network Firewall
- Each log entry includes source/destination IPs, ports, protocols, and AWS account information
- The src_account, src_vpc, and src_region fields are injected during log processing
- Traffic can be filtered by action (allowed/blocked/dropped), account, time range, ports, and protocols
- SNI (Server Name Indication) field contains destination URLs/domains for TLS traffic
- Default time range is 1 hour unless specified otherwise
- Logs are indexed in OpenSearch Serverless with pattern "alert-logs-*"

Security Analysis Guidelines:
- Always highlight blocked traffic as potential security concerns
- Identify unusual traffic patterns or high-volume connections
- Flag traffic to suspicious domains or IP addresses
- Note any traffic on non-standard ports
- Provide context about what normal vs abnormal traffic looks like

When answering questions:
1. Always clarify the time range if not specified (default is 1 hour)
2. Provide clear context about what the data represents
3. Highlight security-relevant findings and potential threats
4. Suggest follow-up queries for deeper analysis
5. Format results in a clear, readable manner with proper categorization
6. Include relevant statistics and summaries
7. Explain the significance of findings in security context

The OpenSearch endpoint is pre-configured and ready to use. Focus on analysis rather than configuration.

Be helpful, accurate, security-focused, and proactive in your responses."""


class FirewallAnalyzerAgent:
    """
    Improved AWS Network Firewall Log Analysis Agent

    This agent provides intelligent analysis of AWS Network Firewall logs
    stored in OpenSearch Serverless, with enhanced error handling,
    simplified response processing, and better user experience.
    """

    def __init__(
        self,
        conversation_history,
        activity_notification,
        agent_model_id,
        enable_debug: bool = False,
    ):
        """
        Initialize the Firewall Analyzer Agent

        Args:
            enable_debug: Enable debug logging for detailed operation tracking
        """
        if enable_debug:
            logging.getLogger("strands").setLevel(logging.DEBUG)
            logging.basicConfig(
                format="%(levelname)s | %(name)s | %(message)s",
                handlers=[logging.StreamHandler()],
            )

        if activity_notification:
            self.activity_notification = activity_notification

        # Initialize the agent with improved configuration
        self.agent = Agent(
            # Use the standard Bedrock model ID for better portability
            model=agent_model_id,
            tools=[
                test_opensearch_connection,
                search_firewall_logs,
                get_blocked_traffic_by_account,
                get_top_urls_by_account,
                get_traffic_summary_by_account,
                get_account_id_from_name,
                current_time,
                calculator,
            ],
            system_prompt=SYSTEM_PROMPT,
        )

        if conversation_history:
            self.agent.messages = conversation_history

        logger.info("Firewall Analyzer Agent initialized successfully")

    def __call__(self, message: str) -> str:
        """
        Make the agent callable directly - simplified response handling

        Args:
            message: User query about firewall logs

        Returns:
            Agent response as a string

        Raises:
            Exception: If the query processing fails
        """
        try:
            logger.debug(f"Processing query: {message}")

            # Strands agents return responses that can be directly converted to string
            response = self.agent(message)

            logger.debug("Query processed successfully")
            return str(response)

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            raise Exception(f"Failed to process firewall log query: {str(e)}") from e

    def query(self, message: str) -> str:
        """
        Alternative query method for explicit calling

        Args:
            message: User query about firewall logs

        Returns:
            Agent response as a string
        """
        return self(message)

    async def query_async(self, message: str) -> str:
        """
        Async query method with streaming support

        Args:
            message: User query about firewall logs

        Returns:
            Complete agent response as a string
        """
        try:
            logger.debug(f"Processing async query: {message}")

            # Get async stream from agent
            agent_stream = self.agent.stream_async(message)

            response_text = ""
            current_tool = None

            # Process streaming events
            async for event in agent_stream:
                if "data" in event:
                    # Accumulate response text
                    response_text += event["data"]
                    # Optionally print for real-time feedback
                    # print(event["data"], end="", flush=True)

                elif "current_tool_use" in event:
                    tool_info = event["current_tool_use"]
                    tool_name = tool_info.get("name")

                    if tool_name and tool_name != current_tool:
                        current_tool = tool_name
                        activity = self._get_activity_description(tool_name)
                        if activity:
                            logger.debug(f"Emitting Activity: {activity}")
                            # await self.emit_status(self.event_emitter, "info", activity, False)
                            # await self.emit_thoughts(activity, self.event_emitter)
                            await self.activity_notification(activity)

            logger.debug("Async query processed successfully")
            return response_text.strip()

        except Exception as e:
            logger.error(f"Error processing async query: {str(e)}")
            raise Exception(
                f"Failed to process async firewall log query: {str(e)}"
            ) from e

    def _get_activity_description(self, tool_name: str) -> Optional[str]:
        """
        Convert tool names to user-friendly activity descriptions

        Args:
            tool_name: Name of the tool being used

        Returns:
            Human-readable description of the activity
        """
        activities = {
            "test_opensearch_connection": "Testing OpenSearch connection and permissions",
            "search_firewall_logs": "Searching firewall logs with specified criteria",
            "get_blocked_traffic_by_account": "Analyzing blocked traffic patterns by account",
            "get_top_urls_by_account": "Identifying most accessed URLs and domains",
            "get_traffic_summary_by_account": "Generating comprehensive traffic summary",
            "get_account_id_by_name": "Resolving AWS account ID from account name",
            "current_time": "Getting current timestamp for time-based analysis",
            "calculator": "Performing statistical calculations on traffic data",
        }
        return activities.get(tool_name)

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the agent and its dependencies

        Returns:
            Dictionary with health check results
        """
        try:
            # Test OpenSearch connection
            connection_result = test_opensearch_connection()

            if (
                isinstance(connection_result, dict)
                and connection_result.get("status") == "success"
            ):
                return {
                    "status": "healthy",
                    "agent": "operational",
                    "opensearch": "connected",
                    "tools": len(self.agent.tools),
                    "model": "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
                    "details": connection_result,
                }
            else:
                return {
                    "status": "degraded",
                    "agent": "operational",
                    "opensearch": "connection_issues",
                    "tools": len(self.agent.tools),
                    "model": "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
                    "details": connection_result,
                }

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "agent": "operational",
                "opensearch": "error",
                "error": str(e),
            }


################### AGENT OPENSEARCH TOOLS ########################

# Global OpenSearch client - initialized on module import
opensearch_client = None


def initialize_opensearch(endpoint, region, role_arn):
    """Initialize the global OpenSearch client with hardcoded values"""
    global opensearch_client

    # Hardcoded values since they never change
    # endpoint = "https://vxoxfikba1rth5rwfmvc.ap-southeast-2.aoss.amazonaws.com"
    # region = "ap-southeast-2"
    # role_arn = "arn:aws:iam::307987194911:role/XAccount-OpenSearch-Firewall-Logs-Role"

    try:
        opensearch_client = OpenSearchClient(endpoint, region, role_arn)
        logger.debug("OpenSearch client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenSearch client: {str(e)}")
        # Don't raise here to allow module import to succeed


# Initialize on module import
# initialize_opensearch()


"""
Improved OpenSearch tools for querying AWS Network Firewall logs
Following Strands SDK best practices with enhanced error handling and documentation
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import boto3
import boto3.dynamodb.conditions
from aws_requests_auth.aws_auth import AWSRequestsAuth
from dateutil import parser as date_parser
from opensearchpy import OpenSearch, RequestsHttpConnection
from strands import tool

logger = logging.getLogger(__name__)


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


@tool
def get_blocked_traffic_by_account(
    account_id: str, time_range_hours: int = 1, max_results: int = 100
) -> Dict[str, Any]:
    """
    Get all blocked traffic for a specific AWS account with security analysis.

    This tool specifically focuses on blocked/dropped traffic for security analysis,
    providing insights into potential threats and attack patterns targeting or
    originating from the specified AWS account.

    Args:
        account_id: AWS account ID to filter by (can be account number or alias)
        time_range_hours: Number of hours to look back (default: 1)
        max_results: Maximum number of results to return (default: 100)

    Returns:
        Dictionary containing blocked traffic results with security context:
        - All standard search result fields
        - Focus on blocked/dropped traffic only
        - Security-relevant metadata and analysis

    Raises:
        ValueError: If account_id is empty or invalid
        Exception: If the search operation fails
    """
    if not account_id or not account_id.strip():
        raise ValueError("account_id cannot be empty")

    logger.debug(f"Analyzing blocked traffic for account: {account_id}")

    try:
        return search_firewall_logs(
            query="",  # No text query, just filter by account and action
            time_range_hours=time_range_hours,
            max_results=max_results,
            account_filter=account_id,
            action_filter="blocked",
        )
    except Exception as e:
        logger.error(
            f"Error getting blocked traffic for account {account_id}: {str(e)}"
        )
        raise Exception(
            f"Failed to retrieve blocked traffic for account {account_id}: {str(e)}"
        ) from e


@tool
def get_top_urls_by_account(
    account_id: str, time_range_hours: int = 1, max_results: int = 50
) -> Dict[str, Any]:
    """
    Get the most commonly accessed URLs/SNIs for a specific AWS account.

    This tool analyzes TLS traffic to identify the most frequently accessed domains
    and URLs, providing insights into traffic patterns and potential security concerns.
    Useful for understanding normal traffic patterns and identifying anomalies.

    Args:
        account_id: AWS account ID to filter by (can be account number or alias)
        time_range_hours: Number of hours to look back (default: 1)
        max_results: Maximum number of URL aggregation buckets (default: 50, max: 100)

    Returns:
        Dictionary containing top URLs/SNIs with detailed statistics:
        - account_id: The account being analyzed
        - time_range_hours: Time period analyzed
        - total_unique_urls: Number of unique URLs found
        - query_time: When the analysis was performed
        - top_urls: Array of URL statistics including:
          - url: The domain/URL accessed
          - total_requests: Number of requests to this URL
          - actions: Breakdown of allowed vs blocked requests
          - security_notes: Any security-relevant observations

    Raises:
        ValueError: If account_id is empty or max_results is invalid
        Exception: If the aggregation query fails
    """
    if not account_id or not account_id.strip():
        raise ValueError("account_id cannot be empty")

    if max_results <= 0 or max_results > 100:
        raise ValueError("max_results must be between 1 and 100")

    if not opensearch_client:
        raise RuntimeError(
            "OpenSearch client not initialized. Please check your AWS credentials and permissions."
        )

    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_range_hours)

        logger.debug(
            f"Analyzing top URLs for account {account_id} from {start_time} to {end_time}"
        )

        # Build aggregation query for top SNIs
        search_body = {
            "size": 0,  # We only want aggregations
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "event.timestamp": {
                                    "gte": start_time.isoformat(),
                                    "lte": end_time.isoformat(),
                                }
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {"term": {"event.src_account.keyword": account_id}},
                                    {
                                        "term": {
                                            "event.dest_account.keyword": account_id
                                        }
                                    },
                                ]
                            }
                        },
                        {"exists": {"field": "event.tls.sni"}},
                    ]
                }
            },
            "aggs": {
                "top_urls": {
                    "terms": {
                        "field": "event.tls.sni.keyword",
                        "size": max_results,
                        "order": {"_count": "desc"},
                    },
                    "aggs": {
                        "actions": {"terms": {"field": "event.alert.action.keyword"}},
                        "protocols": {"terms": {"field": "event.app_proto.keyword"}},
                        "unique_sources": {
                            "cardinality": {"field": "event.src_ip.keyword"}
                        },
                    },
                }
            },
        }

        # Execute search
        response = opensearch_client.client.search(
            index="alert-logs-*", body=search_body, timeout=30
        )

        # Process aggregation results
        aggs = response.get("aggregations", {})
        url_buckets = aggs.get("top_urls", {}).get("buckets", [])

        results = []
        for bucket in url_buckets:
            url = bucket.get("key")
            count = bucket.get("doc_count")

            # Get action breakdown
            actions = {}
            for action_bucket in bucket.get("actions", {}).get("buckets", []):
                actions[action_bucket.get("key")] = action_bucket.get("doc_count")

            # Get protocol breakdown
            protocols = {}
            for proto_bucket in bucket.get("protocols", {}).get("buckets", []):
                protocols[proto_bucket.get("key")] = proto_bucket.get("doc_count")

            # Get unique source count
            unique_sources = bucket.get("unique_sources", {}).get("value", 0)

            # Add security analysis
            security_notes = []
            if actions.get("blocked", 0) > 0:
                security_notes.append(
                    f"Has {actions['blocked']} blocked requests - potential security concern"
                )

            if unique_sources > 10:
                security_notes.append(
                    f"Accessed from {unique_sources} different source IPs - high traffic volume"
                )

            # Check for suspicious domains
            suspicious_indicators = ["temp", "test", "dev", "staging", "internal"]
            if any(indicator in url.lower() for indicator in suspicious_indicators):
                security_notes.append(
                    "Domain name contains potentially suspicious keywords"
                )

            results.append(
                {
                    "url": url,
                    "total_requests": count,
                    "actions": actions,
                    "protocols": protocols,
                    "unique_sources": unique_sources,
                    "security_notes": security_notes,
                }
            )

        logger.debug(f"URL analysis completed: {len(results)} unique URLs found")

        return {
            "account_id": account_id,
            "time_range_hours": time_range_hours,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_unique_urls": len(results),
            "query_time": datetime.utcnow().isoformat(),
            "top_urls": results,
        }

    except Exception as e:
        logger.error(f"Error getting top URLs for account {account_id}: {str(e)}")
        raise Exception(
            f"Failed to analyze top URLs for account {account_id}: {str(e)}"
        ) from e


@tool
def get_traffic_summary_by_account(
    account_id: str, time_range_hours: int = 1
) -> Dict[str, Any]:
    """
    Get a comprehensive traffic summary for a specific AWS account.

    This tool provides detailed traffic analytics including allowed vs blocked counts,
    protocol distribution, top sources and destinations, and security insights.
    Essential for understanding overall traffic patterns and security posture.

    Args:
        account_id: AWS account ID to analyze (can be account number or alias)
        time_range_hours: Number of hours to look back (default: 1)

    Returns:
        Dictionary containing comprehensive traffic summary:
        - account_id: The account being analyzed
        - time_range_hours: Time period analyzed
        - total_events: Total number of firewall events
        - query_time: When the analysis was performed
        - actions: Breakdown of allowed vs blocked traffic counts
        - protocols: Distribution of network protocols (TCP, UDP, etc.)
        - app_protocols: Distribution of application protocols (TLS, HTTP, etc.)
        - top_destinations: Most contacted destination IPs with counts
        - top_sources: Most active source IPs with counts
        - security_summary: High-level security insights and recommendations

    Raises:
        ValueError: If account_id is empty
        Exception: If the aggregation query fails
    """
    if not account_id or not account_id.strip():
        raise ValueError("account_id cannot be empty")

    if not opensearch_client:
        raise RuntimeError(
            "OpenSearch client not initialized. Please check your AWS credentials and permissions."
        )

    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_range_hours)

        logger.debug(
            f"Generating traffic summary for account {account_id} from {start_time} to {end_time}"
        )

        # Build comprehensive aggregation query
        search_body = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "event.timestamp": {
                                    "gte": start_time.isoformat(),
                                    "lte": end_time.isoformat(),
                                }
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {"term": {"event.src_account.keyword": account_id}},
                                    {
                                        "term": {
                                            "event.dest_account.keyword": account_id
                                        }
                                    },
                                ]
                            }
                        },
                    ]
                }
            },
            "aggs": {
                "actions": {
                    "terms": {"field": "event.alert.action.keyword", "size": 10}
                },
                "protocols": {"terms": {"field": "event.proto.keyword", "size": 10}},
                "app_protocols": {
                    "terms": {"field": "event.app_proto.keyword", "size": 10}
                },
                "top_destinations": {
                    "terms": {"field": "event.dest_ip.keyword", "size": 10},
                    "aggs": {
                        "actions": {"terms": {"field": "event.alert.action.keyword"}}
                    },
                },
                "top_sources": {
                    "terms": {"field": "event.src_ip.keyword", "size": 10},
                    "aggs": {
                        "actions": {"terms": {"field": "event.alert.action.keyword"}}
                    },
                },
                "severity_distribution": {
                    "terms": {"field": "event.alert.severity", "size": 5}
                },
                "unique_destinations": {
                    "cardinality": {"field": "event.dest_ip.keyword"}
                },
                "unique_sources": {"cardinality": {"field": "event.src_ip.keyword"}},
            },
        }

        # Execute search
        response = opensearch_client.client.search(
            index="alert-logs-*", body=search_body, timeout=30
        )

        # Process results
        aggs = response.get("aggregations", {})
        total_hits = response.get("hits", {}).get("total", {}).get("value", 0)

        # Process action counts
        actions = {}
        for bucket in aggs.get("actions", {}).get("buckets", []):
            actions[bucket.get("key")] = bucket.get("doc_count")

        # Process protocol counts
        protocols = {}
        for bucket in aggs.get("protocols", {}).get("buckets", []):
            protocols[bucket.get("key")] = bucket.get("doc_count")

        # Process application protocol counts
        app_protocols = {}
        for bucket in aggs.get("app_protocols", {}).get("buckets", []):
            app_protocols[bucket.get("key")] = bucket.get("doc_count")

        # Process top destinations with action breakdown
        top_destinations = []
        for bucket in aggs.get("top_destinations", {}).get("buckets", []):
            dest_actions = {}
            for action_bucket in bucket.get("actions", {}).get("buckets", []):
                dest_actions[action_bucket.get("key")] = action_bucket.get("doc_count")

            top_destinations.append(
                {
                    "ip": bucket.get("key"),
                    "count": bucket.get("doc_count"),
                    "actions": dest_actions,
                }
            )

        # Process top sources with action breakdown
        top_sources = []
        for bucket in aggs.get("top_sources", {}).get("buckets", []):
            src_actions = {}
            for action_bucket in bucket.get("actions", {}).get("buckets", []):
                src_actions[action_bucket.get("key")] = action_bucket.get("doc_count")

            top_sources.append(
                {
                    "ip": bucket.get("key"),
                    "count": bucket.get("doc_count"),
                    "actions": src_actions,
                }
            )

        # Process severity distribution
        severity_distribution = {}
        for bucket in aggs.get("severity_distribution", {}).get("buckets", []):
            severity_distribution[bucket.get("key")] = bucket.get("doc_count")

        # Get unique counts
        unique_destinations = aggs.get("unique_destinations", {}).get("value", 0)
        unique_sources = aggs.get("unique_sources", {}).get("value", 0)

        # Generate security summary
        security_summary = []

        blocked_count = actions.get("blocked", 0)
        allowed_count = actions.get("allowed", 0)
        total_actions = blocked_count + allowed_count

        if total_actions > 0:
            block_percentage = (blocked_count / total_actions) * 100
            if block_percentage > 20:
                security_summary.append(
                    f"High block rate: {block_percentage:.1f}% of traffic blocked - investigate potential threats"
                )
            elif block_percentage > 5:
                security_summary.append(
                    f"Moderate block rate: {block_percentage:.1f}% of traffic blocked - normal security activity"
                )
            else:
                security_summary.append(
                    f"Low block rate: {block_percentage:.1f}% of traffic blocked - minimal security events"
                )

        if unique_destinations > 100:
            security_summary.append(
                f"High connectivity: {unique_destinations} unique destinations contacted - review for unusual patterns"
            )

        if severity_distribution.get(3, 0) > 0:  # High severity events
            security_summary.append(
                f"High severity events detected: {severity_distribution[3]} events require attention"
            )

        # Check for suspicious protocols
        suspicious_protocols = ["ICMP", "GRE"]
        for protocol in suspicious_protocols:
            if protocol in protocols:
                security_summary.append(
                    f"Suspicious protocol detected: {protocol} traffic found"
                )

        logger.debug(f"Traffic summary completed: {total_hits} total events analyzed")

        return {
            "account_id": account_id,
            "time_range_hours": time_range_hours,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_events": total_hits,
            "query_time": datetime.utcnow().isoformat(),
            "actions": actions,
            "protocols": protocols,
            "app_protocols": app_protocols,
            "top_destinations": top_destinations,
            "top_sources": top_sources,
            "severity_distribution": severity_distribution,
            "unique_destinations": unique_destinations,
            "unique_sources": unique_sources,
            "security_summary": security_summary,
        }

    except Exception as e:
        logger.error(
            f"Error getting traffic summary for account {account_id}: {str(e)}"
        )
        raise Exception(
            f"Failed to generate traffic summary for account {account_id}: {str(e)}"
        ) from e


# Additional utility functions for enhanced functionality


def validate_account_id(account_id: str) -> bool:
    """
    Validate AWS account ID format

    Args:
        account_id: Account ID to validate

    Returns:
        True if valid format, False otherwise
    """
    if not account_id:
        return False

    # Check if it's a 12-digit account number
    if account_id.isdigit() and len(account_id) == 12:
        return True

    # Check if it's an account alias (alphanumeric, may contain hyphens)
    if account_id.replace("-", "").replace("_", "").isalnum():
        return True

    return False


def get_time_range_description(hours: int) -> str:
    """
    Get human-readable description of time range

    Args:
        hours: Number of hours

    Returns:
        Human-readable time range description
    """
    if hours < 1:
        return f"{int(hours * 60)} minutes"
    elif hours == 1:
        return "1 hour"
    elif hours < 24:
        return f"{hours} hours"
    elif hours == 24:
        return "1 day"
    else:
        days = hours // 24
        remaining_hours = hours % 24
        if remaining_hours == 0:
            return f"{days} days"
        else:
            return f"{days} days and {remaining_hours} hours"
