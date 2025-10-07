"""Main MCP server application for exposing AI Explorer to external AI agents."""

import logging
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

from .config import settings
from .client.api_client import AIExplorerAPIClient


# Set up logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("AIExplorerMCP")

# Initialize API client (shared across tool calls)
api_client = AIExplorerAPIClient()


def _is_valid_account_id(account_id: str) -> bool:
    """
    Validate Hedera account ID format.
    
    Args:
        account_id: Account ID to validate
        
    Returns:
        True if valid format, False otherwise
    """
    try:
        parts = account_id.split('.')
        if len(parts) != 3:
            return False
        
        # Check if all parts are numeric
        for part in parts:
            int(part)
        
        return True
    except (ValueError, AttributeError):
        return False


@mcp.tool()
async def ask_explorer(
    question: str, 
    network: str = "mainnet",
    account_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ask questions about the Hedera blockchain and get intelligent responses.
    
    This tool can help with transaction analysis, account information,
    network statistics, DeFi protocols, NFTs, and general Hedera ecosystem queries.
    It provides comprehensive blockchain data analysis powered by AI.
    
    Args:
        question: Your question about Hedera blockchain. Examples:
            'What are the recent transactions for account 0.0.123?',
            'Analyze the transaction 0.0.456@1234567890',
            'Show me NFT activity for this collection'
        network: The Hedera network to query (mainnet or testnet). Defaults to "mainnet".
        account_id: Optional Hedera account ID for context (format: 0.0.123).
            When provided, responses may include personalized insights related to this account.
    
    Returns:
        Dict containing the response from AI Explorer or error information
    """
    try:
        logger.info(f"Processing Hedera query: {question[:100]}...")
        
        # Validate network
        valid_networks = ["mainnet", "testnet"]
        if network not in valid_networks:
            return {
                "success": False,
                "error": f"Invalid network '{network}'. Must be one of: {', '.join(valid_networks)}"
            }
        
        # Validate account ID format if provided
        if account_id:
            if not _is_valid_account_id(account_id):
                return {
                    "success": False,
                    "error": f"Invalid account ID format '{account_id}'. Expected format: 0.0.123"
                }
        
        # Connect to API and get response
        async with api_client.connect():
            response = await api_client.get_full_response(
                question=question,
                network=network,
                account_id=account_id
            )
        
        if not response:
            return {
                "success": False,
                "error": "No response received from the Hedera AI Explorer. Please try again."
            }
        
        logger.info(f"Successfully processed query, response length: {len(response)}")
        
        return {
            "success": True,
            "response": response,
            "network": network,
            "account_id": account_id
        }
        
    except Exception as e:
        error_msg = f"Error querying Hedera blockchain: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        return {
            "success": False,
            "error": error_msg
        }