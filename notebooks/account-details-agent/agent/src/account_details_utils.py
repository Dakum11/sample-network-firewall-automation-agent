import os
"""
Account Details Utility Module
Handles DynamoDB connections and account search functionality
"""

import logging
import boto3
import json
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Configuration constants
CROSS_ACCOUNT_ROLE_ARN = os.getenv("CROSS_ACCOUNT_ROLE_ARN", "")
DYNAMODB_TABLE_NAME = "ap-southeast-2-dna-automation-deployment-state"
REGION = "ap-southeast-2"

class AccountDetailsClient:
    """Client for querying AWS account details from DynamoDB"""
    
    def __init__(self, table_name: str = DYNAMODB_TABLE_NAME, region: str = REGION, role_arn: str = CROSS_ACCOUNT_ROLE_ARN):
        self.table_name = table_name
        self.region = region
        self.role_arn = role_arn
        self._table = None
    
    def _assume_role(self):
        """Assume cross-account role to access DynamoDB"""
        sts_client = boto3.client('sts', region_name=self.region)
        response = sts_client.assume_role(
            RoleArn=self.role_arn,
            RoleSessionName="StrandsAgent",
            DurationSeconds=3600
        )
        credentials = response['Credentials']
        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
    
    @property
    def table(self):
        """Lazy-loaded DynamoDB table resource"""
        if self._table is None:
            session = self._assume_role()
            dynamodb = session.resource('dynamodb', region_name=self.region)
            self._table = dynamodb.Table(self.table_name)
        return self._table
    
    def _extract_vpc_info(self, vpc_metadata_str: str) -> Dict:
        """Extract VPC information from metadata JSON string"""
        try:
            vpc_data = json.loads(vpc_metadata_str)
            vpcs = vpc_data.get('Vpcs', [])
            
            if vpcs:
                vpc = vpcs[0]
                vpc_name = None
                for tag in vpc.get('Tags', []):
                    if tag.get('Key') == 'Name':
                        vpc_name = tag.get('Value')
                        break
                
                # Extract subnet details
                subnets = []
                for subnet in vpc.get('Subnets', []):
                    subnet_name = None
                    for tag in subnet.get('Tags', []):
                        if tag.get('Key') == 'Name':
                            subnet_name = tag.get('Value')
                            break
                    
                    subnets.append({
                        'subnet_id': subnet.get('SubnetId'),
                        'subnet_name': subnet_name,
                        'cidr_block': subnet.get('CidrBlock'),
                        'availability_zone': subnet.get('AvailabilityZone'),
                        'available_ips': subnet.get('AvailableIpAddressCount')
                    })
                
                return {
                    'vpc_id': vpc.get('VpcId'),
                    'vpc_name': vpc_name,
                    'main_cidr': vpc.get('CidrBlock'),
                    'subnets_count': len(vpc.get('Subnets', [])),
                    'subnets': subnets,
                    'endpoints': len(vpc.get('Endpoints', []))
                }
        except Exception as e:
            logger.warning(f"Failed to parse VPC metadata: {e}")
        return {}
    
    def get_account_by_id(self, account_id: str) -> Optional[Dict]:
        """Get account details by exact account ID"""
        try:
            response = self.table.get_item(Key={'account-no': account_id})
            item = response.get('Item')
            
            if item:
                vpc_info = {}
                if 'vpc-metadata' in item:
                    vpc_info = self._extract_vpc_info(item['vpc-metadata'])
                
                return {
                    'account-no': item.get('account-no'),
                    'vpc_info': vpc_info
                }
            return None
        except Exception as e:
            logger.error(f"Error getting account by ID {account_id}: {e}")
            return None

    def search_accounts(self, search_term: str) -> List[Dict]:
        """Search accounts by VPC name, account ID, or CIDR range with scoring"""
        try:
            all_items = []
            response = self.table.scan()
            
            # Handle pagination
            while True:
                items = response.get('Items', [])
                for item in items:
                    vpc_info = {}
                    if 'vpc-metadata' in item:
                        vpc_info = self._extract_vpc_info(item['vpc-metadata'])
                    
                    all_items.append({
                        'account-no': item.get('account-no'),
                        'vpc_info': vpc_info
                    })
                
                if 'LastEvaluatedKey' in response:
                    response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                else:
                    break
            
            matches = []
            for account in all_items:
                account_id = account.get('account-no', '')
                vpc_info = account.get('vpc_info', {})
                vpc_name = vpc_info.get('vpc_name', '')
                main_cidr = vpc_info.get('main_cidr', '')
                
                # Exact account ID match (highest priority)
                if search_term == account_id:
                    matches.append({'account': account, 'match_type': 'exact_id', 'score': 100})
                    continue
                
                # CIDR range matching
                if main_cidr and ('/' in search_term or '.' in search_term):
                    if search_term == main_cidr:
                        matches.append({'account': account, 'match_type': 'exact_cidr', 'score': 100})
                        continue
                    if search_term in main_cidr:
                        matches.append({'account': account, 'match_type': 'partial_cidr', 'score': 90})
                        continue
                    if main_cidr.startswith(search_term):
                        search_octets = len(search_term.split('.'))
                        score = 85 + (search_octets * 3)  # More specific = higher score
                        matches.append({'account': account, 'match_type': 'network_cidr', 'score': score})
                        continue
                
                # VPC name matching (simple substring matching)
                if vpc_name:
                    if search_term.lower() == vpc_name.lower():
                        matches.append({'account': account, 'match_type': 'exact_vpc_name', 'score': 95})
                        continue
                    if search_term.lower() in vpc_name.lower():
                        matches.append({'account': account, 'match_type': 'partial_vpc_name', 'score': 80})
            
            # Sort by score and return top matches
            matches.sort(key=lambda x: x['score'], reverse=True)
            return matches
            
        except Exception as e:
            logger.error(f"Error searching accounts for '{search_term}': {e}")
            return []