import json
import boto3
import ipaddress
import base64
import requests
from urllib.parse import unquote

def get_secret(secret_name: str) -> str:
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]

username = json.loads(get_secret("ipam_server/credentials"))["username"]
password = json.loads(get_secret("ipam_server/credentials"))["password"]
SOLIDSERVER_URL = json.loads(get_secret("ipam_server/credentials"))["ipam_url"]

# Encode credentials
HEADERS = {
    'x-ipm-username': base64.b64encode(username.encode()).decode(),
    'x-ipm-password': base64.b64encode(password.encode()).decode(),
    'cache-control': 'no-cache'
}

def calculate_subnet_bounds(subnet_cidr: str) -> dict:
    """
    Calculates start and end IP addresses of a given subnet.

    Args:
        subnet_cidr: CIDR format (e.g., '10.9.56.0/24')

    Returns:
        Dict with network, broadcast, and usable range
    """
    network = ipaddress.ip_network(subnet_cidr, strict=False)
    return {
        "start_ip_addr": str(network.network_address),
        "end_ip_addr": str(network.broadcast_address),
        "first_usable": str(list(network.hosts())[0]) if network.num_addresses > 2 else str(network.network_address),
        "last_usable": str(list(network.hosts())[-1]) if network.num_addresses > 2 else str(network.broadcast_address),
        "total_addresses": network.num_addresses
    }
    

def describe_subnet_owner_region(subnet_object: dict, cidr_range: str = None, ipaddress: str = None) -> str:
    """
    Returns a formatted string describing the subnet CIDR, owner, and region.

    Args:
        subnet_object: A dictionary from EfficientIP IPAM response containing subnet details.
        cidr_range: The CIDR range string (e.g., '10.9.56.0/24')
        ipaddress: An individual IP address string (e.g., '10.9.56.1')

    Returns:
        A human-readable string like:
        "The CIDR range 10.9.56.0/24 is owned by XYZ and is in the region ABC."
    """

    params_raw = subnet_object.get("subnet_class_parameters", "")
    params_decoded = unquote(params_raw)
    params = dict(item.split("=", 1) for item in params_decoded.split("&") if "=" in item)

    owner = params.get("owner", "Unknown")
    region = params.get("region", "Unknown")
    if cidr_range:
        return f"The CIDR range {cidr_range} is owned by {owner} and is in the region {region}."
    elif ipaddress:
        return f"The IP address {ipaddress} is owned by {owner} and is in the region {region}."
    
def check_cidr_range(cidr_range: str) -> dict:
    """
    Check if a specific cidr_range  already exists in IPAM.

    Args:
        cidr_range: CIDR range to validate

    Returns:
        True if cidr_range exists, False otherwise
    """
    url = f"{SOLIDSERVER_URL}/rest/ip_block_subnet_list"
    subnet_bound_response = calculate_subnet_bounds(cidr_range)
    start_ip_addr = subnet_bound_response.get('start_ip_addr')
    end_ip_addr = subnet_bound_response.get('end_ip_addr')
    params = {
        "WHERE": f"start_hostaddr='{start_ip_addr}' and end_hostaddr='{end_ip_addr}'"
    }


    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    
    if response.ok:
        if response.text:
            data = response.json()
            return {"status": "success", "exists": True, "message": describe_subnet_owner_region(data[0], cidr_range=cidr_range)}
        else:
            return {"status": "success", "exists": False, "message": f"The CIDR range {cidr_range} entry does not exist in IPAM"}
    return {"status": "error", "error": response.text}

def check_ip_addresses(ip_address: str = None) -> dict:
    """
    Validate if the given IP address is available in IPAM.

    Args:
        ip_address: IP address to validate (e.g., '10.10.128.24')
    """
    url = f"{SOLIDSERVER_URL}/rest/ip_address_list"
    params = {}
    if ip_address:
        params["WHERE"] = f"hostaddr='{ip_address}'"
    response = requests.get(url, headers=HEADERS, params=params, verify=False)
    if response.ok:
        if response.text:
            data = response.json()
            return {"status": "success", "exists": True, "message": describe_subnet_owner_region(data[0], ipaddress=ip_address)}
        else:
            return {"status": "success", "exists": False, "message": f"{ip_address} entry does not exist in IPAM"}
    return {"status": "error", "error": response.text}


def classify_ip_or_cidr(value: str) -> str:
    """
    Classifies whether the input IP or CIDR block is private or public.

    Args:
        value: A string representing an IP address or a CIDR block (e.g., '10.0.0.1', '192.168.1.0/24')

    Returns:
        One of: 'private', 'public' or 'invalid'
    """
    try:
        # Try parsing as a network (CIDR block)
        network = ipaddress.ip_network(value, strict=False)
        if network.is_private:
            return "private"
        else:
            return "public"
    except ValueError:
        try:
            # Fallback: try parsing as a single IP
            ip = ipaddress.ip_address(value)
            if ip.is_private:
                return "private"
            else:
                return "public"
        except ValueError:
            return "invalid"