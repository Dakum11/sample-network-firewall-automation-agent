"""
Account Details Tool for Strands Agent Integration
Provides the @tool decorator function for easy integration with any Strands agent
"""

import logging
from strands import tool
from account_details_utils import AccountDetailsClient, DYNAMODB_TABLE_NAME, REGION, CROSS_ACCOUNT_ROLE_ARN

logger = logging.getLogger(__name__)

# Initialize shared client instance
_account_client = AccountDetailsClient(DYNAMODB_TABLE_NAME, REGION, CROSS_ACCOUNT_ROLE_ARN)

@tool
def query_account_details(account_identifier: str):
    """
    Query AWS account details from DynamoDB.
    
    This tool can search by:
    - Account ID (12-digit number)
    - VPC name (exact or partial match)
    - CIDR range (exact or partial match)
    
    Args:
        account_identifier: Account ID, VPC name, or CIDR range to search for
    
    Returns:
        Account details including VPC information and metadata
    """
    try:
        logger.info(f"Querying account details for: {account_identifier}")
        
        # Direct account ID lookup
        if account_identifier.isdigit() and len(account_identifier) == 12:
            account = _account_client.get_account_by_id(account_identifier)
            if account:
                vpc_info = account.get('vpc_info', {})
                return {
                    "found": True,
                    "match_type": "exact_id",
                    "account_id": account.get('account-no'),
                    "vpc_id": vpc_info.get('vpc_id'),
                    "vpc_name": vpc_info.get('vpc_name'),
                    "main_cidr": vpc_info.get('main_cidr'),
                    "subnets_count": vpc_info.get('subnets_count'),
                    "subnets": vpc_info.get('subnets', []),
                    "endpoints_count": vpc_info.get('endpoints')
                }
        else:
            # Search-based lookup
            matches = _account_client.search_accounts(account_identifier)
            if matches:
                best_match = matches[0]
                account = best_match['account']
                vpc_info = account.get('vpc_info', {})
                
                return {
                    "found": True,
                    "match_type": best_match['match_type'],
                    "confidence_score": best_match['score'],
                    "account_id": account.get('account-no'),
                    "vpc_id": vpc_info.get('vpc_id'),
                    "vpc_name": vpc_info.get('vpc_name'),
                    "main_cidr": vpc_info.get('main_cidr'),
                    "subnets_count": vpc_info.get('subnets_count'),
                    "subnets": vpc_info.get('subnets', []),
                    "endpoints_count": vpc_info.get('endpoints'),
                    "alternatives": [
                        {
                            "account_id": m['account'].get('account-no'),
                            "vpc_name": m['account'].get('vpc_info', {}).get('vpc_name'),
                            "main_cidr": m['account'].get('vpc_info', {}).get('main_cidr'),
                            "match_type": m['match_type'],
                            "score": m['score']
                        } for m in matches[1:5]  # Show top 4 alternatives
                    ]
                }
        
        return {
            "found": False,
            "searched_for": account_identifier,
            "message": f"No account found matching '{account_identifier}'"
        }
        
    except Exception as e:
        logger.error(f"Error in query_account_details: {str(e)}")
        return {
            "error": str(e),
            "found": False,
            "searched_for": account_identifier
        }