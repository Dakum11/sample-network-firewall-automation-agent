"""
Account Details Utility Module
Handles DynamoDB connections and account search functionality
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import boto3
from thefuzz import fuzz

logger = logging.getLogger(__name__)

# Configuration constants (loaded from environment variables)
CROSS_ACCOUNT_ROLE_ARN = os.getenv('CROSS_ACCOUNT_ROLE_ARN', '')
DYNAMODB_DEPLOYMENT_STATE_TABLE_SUFFIX = os.getenv('DYNAMODB_DEPLOYMENT_STATE_TABLE_SUFFIX', '-deployment-state')
DYNAMODB_ACCOUNT_METADATA_TABLE_NAME = os.getenv('DYNAMODB_ACCOUNT_METADATA_TABLE_NAME', 'account-metadata')


class AccountDetailsClient:
    """Client for querying AWS account details from DynamoDB"""

    def __init__(
        self,
        region: str,
        deployment_state_table_suffix: str = DYNAMODB_DEPLOYMENT_STATE_TABLE_SUFFIX,
        account_metadata_table_name: str = DYNAMODB_ACCOUNT_METADATA_TABLE_NAME,
        role_arn: str = CROSS_ACCOUNT_ROLE_ARN,
    ):
        self.deployment_state_table_name = region + deployment_state_table_suffix
        self.account_metadata_table_name = account_metadata_table_name
        self.role_arn = role_arn
        self._deployment_state_table = None
        self._account_metadata_table = None

    def _get_session(self):
        """Get a boto3 session — assumes cross-account role if configured, otherwise uses default credentials"""
        if self.role_arn:
            sts_client = boto3.client("sts", region_name=os.getenv('AWS_REGION', 'us-east-1'))
            response = sts_client.assume_role(
                RoleArn=self.role_arn, RoleSessionName="StrandsAgent", DurationSeconds=3600
            )
            credentials = response["Credentials"]
            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )
        else:
            return boto3.Session()

    @property
    def deployment_state_table(self):
        """Lazy-loaded DynamoDB table resources"""
        if self._deployment_state_table is None:
            session = self._get_session()
            dynamodb = session.resource("dynamodb", region_name=os.getenv('AWS_REGION', 'us-east-1'))
            self._deployment_state_table = dynamodb.Table(
                self.deployment_state_table_name
            )
        return self._deployment_state_table

    @property
    def account_metadata_table(self):
        """Lazy-loaded DynamoDB table resources"""
        if self._account_metadata_table is None:
            session = self._get_session()
            dynamodb = session.resource("dynamodb", region_name=os.getenv('AWS_REGION', 'us-east-1'))
            self._account_metadata_table = dynamodb.Table(
                self.account_metadata_table_name
            )
        return self._account_metadata_table

    def _extract_vpc_info(self, vpc_metadata_str: str) -> Dict:
        """Extract VPC information from metadata JSON string"""
        try:
            vpc_data = json.loads(vpc_metadata_str)
            vpcs = vpc_data.get("Vpcs", [])

            if vpcs:
                vpc = vpcs[0]
                vpc_name = None
                for tag in vpc.get("Tags", []):
                    if tag.get("Key") == "Name":
                        vpc_name = tag.get("Value")
                        break

                # Extract subnet details
                subnets = []
                for subnet in vpc.get("Subnets", []):
                    subnet_name = None
                    for tag in subnet.get("Tags", []):
                        if tag.get("Key") == "Name":
                            subnet_name = tag.get("Value")
                            break

                    subnets.append(
                        {
                            "subnet_id": subnet.get("SubnetId"),
                            "subnet_name": subnet_name,
                            "cidr_block": subnet.get("CidrBlock"),
                            "availability_zone": subnet.get("AvailabilityZone"),
                            "available_ips": subnet.get("AvailableIpAddressCount"),
                        }
                    )

                return {
                    "vpc_id": vpc.get("VpcId"),
                    "vpc_name": vpc_name,
                    "main_cidr": vpc.get("CidrBlock"),
                    "subnets_count": len(vpc.get("Subnets", [])),
                    "subnets": subnets,
                    "endpoints": len(vpc.get("Endpoints", [])),
                }
        except Exception as e:
            logger.warning(f"Failed to parse VPC metadata: {e}")
        return {}

    def get_account_by_id(self, account_id: str) -> Optional[Dict]:
        """Get account details by exact account ID"""
        try:
            response = self.deployment_state_table.get_item(
                Key={"account-no": account_id}
            )
            item = response.get("Item")

            if item:
                account_no = item.get("account-no")

                vpc_info = {}
                if "vpc-metadata" in item:
                    vpc_info = self._extract_vpc_info(item["vpc-metadata"])

                response = self.account_metadata_table.get_item(
                    Key={"account-no": account_id}
                )
                item = response.get("Item")
                account_name = item.get("account-name") if item else None

                return {
                    "account-no": account_no,
                    "account-name": account_name,
                    "vpc_info": vpc_info,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting account by ID {account_id}: {e}")
            return None

    def search_accounts(self, search_term: str) -> List[Dict]:
        """Search accounts by Account name, VPC name, account ID, or CIDR range with scoring"""
        try:
            # Step 1: Scan account metadata table and build lookup dictionary
            print("Scanning account metadata table...")
            account_metadata_lookup = {}
            account_metadata_response = self.account_metadata_table.scan()

            while True:
                for item in account_metadata_response.get("Items", []):
                    account_no = item.get("account-no")
                    if account_no:
                        account_metadata_lookup[account_no] = item.get("account-name")

                if "LastEvaluatedKey" in account_metadata_response:
                    account_metadata_response = self.account_metadata_table.scan(
                        ExclusiveStartKey=account_metadata_response["LastEvaluatedKey"]
                    )
                else:
                    break

            print(f"Loaded {len(account_metadata_lookup)} account metadata records")

            # Step 2: Scan deployment state table and join with metadata
            print("Scanning deployment state table...")
            all_items = []
            deployment_state_response = self.deployment_state_table.scan()

            while True:
                deployment_state_items = deployment_state_response.get("Items", [])
                for item in deployment_state_items:
                    account_no = item.get("account-no")

                    # Extract VPC info
                    vpc_info = {}
                    if "vpc-metadata" in item:
                        vpc_info = self._extract_vpc_info(item["vpc-metadata"])

                    # Fast lookup from dictionary instead of individual DynamoDB calls
                    account_name = account_metadata_lookup.get(account_no)

                    all_items.append(
                        {
                            "account-no": account_no,
                            "account-name": account_name,
                            "vpc_info": vpc_info,
                        }
                    )

                if "LastEvaluatedKey" in deployment_state_response:
                    deployment_state_response = self.deployment_state_table.scan(
                        ExclusiveStartKey=deployment_state_response["LastEvaluatedKey"]
                    )
                else:
                    break

            print(f"Processed {len(all_items)} accounts")

            matches = []
            for account in all_items:
                account_id = account.get("account-no", "")
                account_name = account.get("account-name", "")
                vpc_info = account.get("vpc_info", {})
                vpc_name = vpc_info.get("vpc_name", "")
                main_cidr = vpc_info.get("main_cidr", "")

                # Exact account ID match (highest priority)
                if search_term == account_id:
                    matches.append(
                        {"account": account, "match_type": "exact_id", "score": 100}
                    )
                    continue

                # Account name matching (simple substring matching)
                if account_name:
                    if search_term.lower() == account_name.lower():
                        matches.append(
                            {
                                "account": account,
                                "match_type": "exact_account_name",
                                "score": 95,
                            }
                        )
                        continue
                    matches.append(
                        {
                            "account": account,
                            "match_type": "partial_account_name",
                            "score": fuzz.ratio(
                                search_term.lower(), account_name.lower()
                            ),
                        }
                    )

                # CIDR range matching
                if main_cidr and ("/" in search_term or "." in search_term):
                    if search_term == main_cidr:
                        matches.append(
                            {
                                "account": account,
                                "match_type": "exact_cidr",
                                "score": 100,
                            }
                        )
                        continue
                    if search_term in main_cidr:
                        matches.append(
                            {
                                "account": account,
                                "match_type": "partial_cidr",
                                "score": 90,
                            }
                        )
                        continue
                    if main_cidr.startswith(search_term):
                        search_octets = len(search_term.split("."))
                        score = 85 + (search_octets * 3)  # More specific = higher score
                        matches.append(
                            {
                                "account": account,
                                "match_type": "network_cidr",
                                "score": score,
                            }
                        )
                        continue

                # VPC name matching (simple substring matching)
                if vpc_name:
                    if search_term.lower() == vpc_name.lower():
                        matches.append(
                            {
                                "account": account,
                                "match_type": "exact_vpc_name",
                                "score": 95,
                            }
                        )
                        continue
                    if search_term.lower() in vpc_name.lower():
                        matches.append(
                            {
                                "account": account,
                                "match_type": "partial_vpc_name",
                                "score": 80,
                            }
                        )

            # Sort by score and return top matches
            matches.sort(key=lambda x: x["score"], reverse=True)
            return matches

        except Exception as e:
            logger.error(f"Error searching accounts for '{search_term}': {e}")
            return []
