################### DYNAMODB CLIENT AND TOOLS ########################


class DynamoDBClient:
    """
    DynamoDB client for cross-account access to account metadata
    """

    def __init__(
        self, table_name: str, region: str = "ap-southeast-2", role_arn: str = None
    ):
        self.table_name = table_name
        self.region = region
        self.role_arn = role_arn
        self._client = None
        self._table = None

    def _assume_role(self):
        """Assume the cross-account IAM role and return session"""
        if not self.role_arn:
            return boto3.Session()

        try:
            sts_client = boto3.client("sts", region_name=self.region)
            response = sts_client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName="AccountMetadataAccess",
                DurationSeconds=3600,
            )

            credentials = response["Credentials"]
            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )
        except Exception as e:
            logger.error(f"Failed to assume role {self.role_arn}: {str(e)}")
            raise RuntimeError(f"Role assumption failed: {str(e)}") from e

    @property
    def table(self):
        """Lazy initialization of DynamoDB table resource"""
        if self._table is None:
            try:
                session = self._assume_role()
                dynamodb = session.resource("dynamodb", region_name=self.region)
                self._table = dynamodb.Table(self.table_name)
                logger.debug(f"DynamoDB table initialized: {self.table_name}")
            except Exception as e:
                logger.error(f"Failed to initialize DynamoDB table: {str(e)}")
                raise RuntimeError(
                    f"DynamoDB table initialization failed: {str(e)}"
                ) from e
        return self._table

    def get_account_id_by_name(
        self, account_name: str, fuzzy_match: bool = True, return_all: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get account ID by account name using scan operation

        Args:
            account_name: The account name to search for
            fuzzy_match: If True, also search for partial matches
            return_all: If True, return all matches instead of just the best one

        Returns:
            Dict with account_id and match_type, or None if not found
        """
        try:
            # First try exact match
            response = self.table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr("account-name").eq(
                    account_name
                ),
                ProjectionExpression="#account_no, #account_name",
                ExpressionAttributeNames={
                    "#account_no": "account-no",
                    "#account_name": "account-name",
                },
            )

            items = response.get("Items", [])
            if items:
                if return_all:
                    return {"match_type": "exact", "all_matches": items}
                else:
                    return {
                        "account_id": items[0].get("account-no"),
                        "account_name": items[0].get("account-name"),
                        "match_type": "exact",
                        "all_matches": items,
                    }

            # If no exact match and fuzzy enabled, try partial matches
            if fuzzy_match:
                response = self.table.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr(
                        "account-name"
                    ).contains(account_name),
                    ProjectionExpression="#account_no, #account_name",
                    ExpressionAttributeNames={
                        "#account_no": "account-no",
                        "#account_name": "account-name",
                    },
                )

                items = response.get("Items", [])
                if items:
                    # Return all matches, sorted by relevance
                    matches = sorted(
                        items, key=lambda x: len(x.get("account-name", ""))
                    )

                    if return_all:
                        return {"match_type": "partial", "all_matches": matches}
                    else:
                        best_match = matches[0]
                        return {
                            "account_id": best_match.get("account-no"),
                            "account_name": best_match.get("account-name"),
                            "match_type": "partial",
                            "all_matches": matches,
                        }

            return None

        except Exception as e:
            logger.error(f"Error scanning DynamoDB table: {str(e)}")
            raise Exception(f"Failed to query account metadata: {str(e)}") from e


# Global DynamoDB client
dynamodb_client = None


def initialize_dynamodb(table_name: str, region: str, role_arn: str = None):
    """Initialize the global DynamoDB client"""
    global dynamodb_client
    try:
        dynamodb_client = DynamoDBClient(table_name, region, role_arn)
        logger.debug("DynamoDB client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize DynamoDB client: {str(e)}")


@tool
def get_account_id_from_name(
    account_name: str, fuzzy_match: bool = False, return_all: bool = False
) -> Dict[str, Any]:
    """
    Get AWS account ID from account name using DynamoDB lookup.

    This tool searches the account metadata table to find the account ID
    corresponding to the provided account name. Supports fuzzy matching
    for partial name matches.

    Args:
        account_name: The account name to search for
        fuzzy_match: If True, also search for partial matches when exact match fails

    Returns:
        Dictionary containing:
        - account_name: The searched account name
        - account_id: The found account ID (if any)
        - matched_name: The actual account name that was matched (for fuzzy matches)
        - match_type: 'exact', 'partial', or 'none'
        - found: Boolean indicating if account was found
        - query_time: When the lookup was performed

    Raises:
        RuntimeError: If DynamoDB client is not initialized
        Exception: If the lookup operation fails
    """
    if not dynamodb_client:
        raise RuntimeError(
            "DynamoDB client not initialized. Please check configuration."
        )

    if not account_name or not account_name.strip():
        raise ValueError("account_name cannot be empty")

    try:
        logger.debug(f"Looking up account ID for name: {account_name}")

        result = dynamodb_client.get_account_id_by_name(
            account_name.strip(), fuzzy_match, return_all
        )

        if result:
            response_data = {
                "account_name": account_name,
                "account_id": result["account_id"],
                "matched_name": result["account_name"],
                "match_type": result["match_type"],
                "found": True,
                "query_time": datetime.utcnow().isoformat(),
            }

            # Include all matches if available
            if "all_matches" in result:
                response_data["all_matches"] = [
                    {
                        "account_id": match.get("account-no"),
                        "account_name": match.get("account-name"),
                    }
                    for match in result["all_matches"]
                ]

            return response_data
        else:
            return {
                "account_name": account_name,
                "account_id": None,
                "matched_name": None,
                "match_type": "none",
                "found": False,
                "query_time": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Error looking up account name {account_name}: {str(e)}")
        raise Exception(
            f"Failed to lookup account ID for name {account_name}: {str(e)}"
        ) from e
