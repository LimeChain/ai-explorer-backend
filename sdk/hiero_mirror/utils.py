"""Utility functions for working with Hiero Mirror Node data."""

import re
from datetime import datetime
from typing import Optional, Union, Dict, Any
from decimal import Decimal


class EntityId:
    """Represents a Hiero entity ID in shard.realm.num format."""
    
    def __init__(self, shard: int, realm: int, num: int) -> None:
        self.shard = shard
        self.realm = realm
        self.num = num
    
    def __str__(self) -> str:
        return f"{self.shard}.{self.realm}.{self.num}"
    
    def __repr__(self) -> str:
        return f"EntityId(shard={self.shard}, realm={self.realm}, num={self.num})"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EntityId):
            return False
        return self.shard == other.shard and self.realm == other.realm and self.num == other.num
    
    def __hash__(self) -> int:
        return hash((self.shard, self.realm, self.num))


def parse_entity_id(entity_id: str) -> EntityId:
    """Parse a string entity ID into an EntityId object.
    
    Args:
        entity_id: String in format "shard.realm.num", "realm.num", or "num"
        
    Returns:
        EntityId object
        
    Raises:
        ValueError: If the entity ID format is invalid
    """
    if not entity_id:
        raise ValueError("Entity ID cannot be empty")
    
    # Handle different formats
    parts = entity_id.split(".")
    
    if len(parts) == 1:
        # Just the num part
        return EntityId(0, 0, int(parts[0]))
    elif len(parts) == 2:
        # realm.num
        return EntityId(0, int(parts[0]), int(parts[1]))
    elif len(parts) == 3:
        # shard.realm.num
        return EntityId(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        raise ValueError(f"Invalid entity ID format: {entity_id}")


def format_entity_id(entity_id: EntityId) -> str:
    """Format an EntityId object as a string.
    
    Args:
        entity_id: EntityId object
        
    Returns:
        String in format "shard.realm.num"
    """
    return str(entity_id)


def validate_entity_id(entity_id: str) -> bool:
    """Validate if a string is a valid entity ID format.
    
    Args:
        entity_id: String to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        parse_entity_id(entity_id)
        return True
    except (ValueError, TypeError):
        return False


def to_timestamp(dt: datetime) -> str:
    """Convert a datetime object to Hiero timestamp format.
    
    Args:
        dt: datetime object
        
    Returns:
        Timestamp string in format "seconds.nanoseconds"
    """
    # Convert to Unix timestamp with nanosecond precision
    timestamp = dt.timestamp()
    seconds = int(timestamp)
    nanoseconds = int((timestamp - seconds) * 1_000_000_000)
    return f"{seconds}.{nanoseconds:09d}"


def from_timestamp(timestamp: str) -> datetime:
    """Convert a Hiero timestamp string to a datetime object.
    
    Args:
        timestamp: Timestamp string in format "seconds.nanoseconds"
        
    Returns:
        datetime object
    """
    if "." in timestamp:
        seconds_str, nanoseconds_str = timestamp.split(".", 1)
        seconds = int(seconds_str)
        # Pad nanoseconds to 9 digits
        nanoseconds_str = nanoseconds_str.ljust(9, "0")[:9]
        nanoseconds = int(nanoseconds_str)
        microseconds = nanoseconds // 1000
        return datetime.fromtimestamp(seconds + microseconds / 1_000_000)
    else:
        return datetime.fromtimestamp(int(timestamp))


def parse_timestamp(timestamp: str) -> Dict[str, Union[str, int]]:
    """Parse a timestamp string into its components.
    
    Args:
        timestamp: Timestamp string
        
    Returns:
        Dictionary with 'seconds' and 'nanoseconds' keys
    """
    if "." in timestamp:
        seconds_str, nanoseconds_str = timestamp.split(".", 1)
        return {
            "seconds": int(seconds_str),
            "nanoseconds": int(nanoseconds_str.ljust(9, "0")[:9])
        }
    else:
        return {
            "seconds": int(timestamp),
            "nanoseconds": 0
        }


def format_balance(balance: Union[int, str], decimals: int = 8) -> str:
    """Format a balance with proper decimal places.
    
    Args:
        balance: Balance value in smallest units
        decimals: Number of decimal places
        
    Returns:
        Formatted balance string
    """
    if isinstance(balance, str):
        balance = int(balance)
    
    # Convert to decimal with proper precision
    decimal_balance = Decimal(balance) / Decimal(10 ** decimals)
    
    # Format with trailing zeros removed
    formatted = f"{decimal_balance:.{decimals}f}".rstrip("0").rstrip(".")
    
    # Always show at least one decimal place for non-zero balances
    if "." not in formatted and balance != 0:
        formatted += ".0"
    
    return formatted


def format_hbar_balance(balance: Union[int, str]) -> str:
    """Format an HBAR balance (8 decimal places).
    
    Args:
        balance: Balance in tinybars
        
    Returns:
        Formatted HBAR balance string
    """
    return format_balance(balance, 8)


def is_valid_evm_address(address: str) -> bool:
    """Check if a string is a valid EVM address.
    
    Args:
        address: Address string to validate
        
    Returns:
        True if valid EVM address, False otherwise
    """
    # Remove 0x prefix if present
    addr = address.lower()
    if addr.startswith("0x"):
        addr = addr[2:]
    
    # Check if it's 40 hex characters
    return len(addr) == 40 and re.match(r"^[0-9a-f]{40}$", addr) is not None


def is_valid_transaction_hash(hash_str: str) -> bool:
    """Check if a string is a valid transaction hash.
    
    Args:
        hash_str: Hash string to validate
        
    Returns:
        True if valid transaction hash, False otherwise
    """
    # Remove 0x prefix if present
    hash_clean = hash_str.lower()
    if hash_clean.startswith("0x"):
        hash_clean = hash_clean[2:]
    
    # Check for 32-byte (64 hex chars) Ethereum hash or 48-byte (96 hex chars) Hedera hash
    return (
        (len(hash_clean) == 64 and re.match(r"^[0-9a-f]{64}$", hash_clean) is not None) or
        (len(hash_clean) == 96 and re.match(r"^[0-9a-f]{96}$", hash_clean) is not None)
    )


def parse_transaction_id(transaction_id: str) -> Dict[str, Union[str, int]]:
    """Parse a transaction ID string into its components.
    
    Args:
        transaction_id: Transaction ID in format "shard.realm.num-seconds-nanos"
        
    Returns:
        Dictionary with parsed components
    """
    pattern = r"^(\d+)\.(\d+)\.(\d+)-(\d+)-(\d+)$"
    match = re.match(pattern, transaction_id)
    
    if not match:
        raise ValueError(f"Invalid transaction ID format: {transaction_id}")
    
    shard, realm, num, seconds, nanos = match.groups()
    
    return {
        "account_id": f"{shard}.{realm}.{num}",
        "valid_start_seconds": int(seconds),
        "valid_start_nanos": int(nanos),
        "shard": int(shard),
        "realm": int(realm),
        "num": int(num)
    }


def build_query_params(**kwargs: Any) -> Dict[str, str]:
    """Build query parameters, filtering out None values.
    
    Args:
        **kwargs: Query parameters
        
    Returns:
        Dictionary of query parameters with None values removed
    """
    params = {}
    for key, value in kwargs.items():
        if value is not None:
            # Convert key from snake_case to dot notation for certain parameters
            if key in ["account_id", "token_id", "spender_id", "sender_id", "receiver_id", "node_id", "file_id", "schedule_id", "contract_id"]:
                key = key.replace("_", ".")
            elif key == "account_balance":
                key = "account.balance"
            elif key == "account_publickey":
                key = "account.publickey"
            elif key == "block_number":
                key = "block.number"
            elif key == "block_hash":
                key = "block.hash"
            elif key == "transaction_index":
                key = "transaction.index"
            elif key == "transaction_hash":
                key = "transaction.hash"
            elif key == "serial_number":
                key = "serialnumber"
            elif key == "transaction_type":
                key = "transactiontype"
            elif key == "sequence_number":
                key = "sequencenumber"
            
            params[key] = str(value)
    
    return params


def normalize_order(order: Optional[str]) -> Optional[str]:
    """Normalize order parameter to lowercase.
    
    Args:
        order: Order parameter ("asc", "desc", or None)
        
    Returns:
        Normalized order parameter
    """
    if order is None:
        return None
    return order.lower()


def validate_limit(limit: Optional[int]) -> Optional[int]:
    """Validate and normalize limit parameter.
    
    Args:
        limit: Limit parameter
        
    Returns:
        Validated limit parameter
        
    Raises:
        ValueError: If limit is invalid
    """
    if limit is None:
        return None
    
    if not isinstance(limit, int):
        raise ValueError("Limit must be an integer")
    
    if limit < 1:
        raise ValueError("Limit must be greater than 0")
    
    if limit > 100:
        raise ValueError("Limit must be 100 or less")
    
    return limit


def get_network_urls() -> Dict[str, str]:
    """Get the default network URLs for different Hiero networks.
    
    Returns:
        Dictionary mapping network names to URLs
    """
    return {
        "mainnet": "https://mainnet.mirrornode.hedera.com",
        "testnet": "https://testnet.mirrornode.hedera.com",
        "previewnet": "https://previewnet.mirrornode.hedera.com"
    }


def extract_next_link(links: Optional[Dict[str, Optional[str]]]) -> Optional[str]:
    """Extract the next link from a response links object.
    
    Args:
        links: Links object from API response
        
    Returns:
        Next link URL or None if no next link
    """
    if links is None:
        return None
    
    next_link = links.get("next")
    if next_link is None:
        return None
    
    # Extract just the query parameters from the next link
    if "?" in next_link:
        return next_link.split("?", 1)[1]
    
    return next_link