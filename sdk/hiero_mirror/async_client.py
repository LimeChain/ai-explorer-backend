"""Asynchronous client for Hiero Mirror Node REST API."""

import asyncio
import logging
import time

from timeit import default_timer as timer

from typing import Dict, List, Optional, AsyncIterator, Any
from urllib.parse import parse_qs
import httpx
from pydantic import ValidationError

from .models import *
from .exceptions import *
from .utils import (
    build_query_params,
    normalize_order,
    validate_limit,
    get_network_urls,
    extract_next_link,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FULL_PAGE_SIZE = 100
FALLBACK_DAYS = 60
SECONDS_PER_DAY = 24 * 60 * 60

class AsyncMirrorNodeClient:
    """Asynchronous client for Hiero Mirror Node REST API."""

    def __init__(
        self,
        base_url: str,
        request_timeout: int,
        timeout: float = 30.0,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        user_agent: str = "hiero-mirror-node-sdk/0.134.0",
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize the async client.

        Args:
            base_url: Base URL of the Mirror Node API
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            retry_delay: Initial delay between retries in seconds
            retry_backoff: Backoff multiplier for retry delays
            user_agent: User agent string for requests
            headers: Additional headers to include in requests
        """
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff

        # Set up headers
        default_headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)

        # Initialize HTTP client
        self._client = httpx.AsyncClient(
            headers=default_headers,
            timeout=timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "AsyncMirrorNodeClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


    @classmethod
    def for_network(cls, network: str, **kwargs) -> "AsyncMirrorNodeClient":
        """Create an async client for a specific network."""
        return cls(get_network_urls()[network], **kwargs)

    @classmethod
    def for_mainnet(cls, **kwargs) -> "AsyncMirrorNodeClient":
        """Create an async client for Hiero mainnet."""
        return cls(get_network_urls()["mainnet"], **kwargs)

    @classmethod
    def for_testnet(cls, **kwargs) -> "AsyncMirrorNodeClient":
        """Create an async client for Hiero testnet."""
        return cls(get_network_urls()["testnet"], **kwargs)

    @classmethod
    def for_previewnet(cls, **kwargs) -> "AsyncMirrorNodeClient":
        """Create an async client for Hiero previewnet."""
        return cls(get_network_urls()["previewnet"], **kwargs)

    async def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic."""
        url = f"{self.base_url}{path}"
        
        for attempt in range(self.retry_attempts + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                )
                
                # Handle successful responses
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as e:
                        raise MirrorNodeException(f"Invalid JSON response: {e}") from e
                
                # Handle error responses
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = None
                
                # Create appropriate exception
                exception = create_exception_from_response(response.status_code, error_data)
                
                # Retry on server errors and rate limits
                if response.status_code >= 500 or response.status_code == 429:
                    if attempt < self.retry_attempts:
                        delay = self.retry_delay * (self.retry_backoff ** attempt)
                        await asyncio.sleep(delay)
                        continue
                
                raise exception
                
            except httpx.RequestError as e:
                if attempt < self.retry_attempts:
                    delay = self.retry_delay * (self.retry_backoff ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise NetworkError(f"Network error: {e}", e)
        
        # This should never be reached
        raise MirrorNodeException("Maximum retry attempts exceeded")

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request."""
        return await self._make_request("GET", path, params)

    async def _post(self, path: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request."""
        return await self._make_request("POST", path, json_data=json_data)

    def _parse_response(self, response_data: Dict[str, Any], model_class) -> Any:
        """Parse response data into a Pydantic model."""
        try:
            return model_class.parse_obj(response_data)
        except ValidationError as e:
            raise MirrorNodeException(f"Response validation error: {e}") from e

    # Account endpoints

    async def get_accounts(
        self,
        account_balance: Optional[str] = None,
        account_id: Optional[str] = None,
        account_publickey: Optional[str] = None,
        balance: Optional[bool] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
    ) -> AccountsResponse:
        """Get accounts on the network.

        Args:
            account_balance: Filter by account balance
            account_id: Filter by account ID
            account_publickey: Filter by account public key
            balance: Whether to include balance information
            limit: Maximum number of results
            order: Sort order (asc/desc)

        Returns:
            AccountsResponse with account information
        """
        params = build_query_params(
            account_balance=account_balance,
            account_id=account_id,
            account_publickey=account_publickey,
            balance=balance,
            limit=validate_limit(limit),
            order=normalize_order(order),
        )
        
        response = await self._get("/api/v1/accounts", params)
        return self._parse_response(response, AccountsResponse)

    async def get_account(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
        transaction_type: Optional[str] = None,
        transactions: Optional[bool] = None,
    ) -> AccountBalanceTransactions:
        """Get account information by ID, alias, or EVM address.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of transactions to return
            order: Sort order for transactions (asc/desc)
            timestamp: Filter by timestamp
            transaction_type: Filter by transaction type
            transactions: Whether to include transactions

        Returns:
            AccountBalanceTransactions with account and transaction information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            timestamp=timestamp,
            transactiontype=transaction_type,
            transactions=transactions,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}", params)
        return self._parse_response(response, AccountBalanceTransactions)

    async def get_account_nfts(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        serial_number: Optional[str] = None,
        spender_id: Optional[str] = None,
        token_id: Optional[str] = None,
    ) -> NftsResponse:
        """Get NFTs for an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            serial_number: Filter by serial number
            spender_id: Filter by spender ID
            token_id: Filter by token ID

        Returns:
            NftsResponse with NFT information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            serialnumber=serial_number,
            spender_id=spender_id,
            token_id=token_id,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/nfts", params)
        return self._parse_response(response, NftsResponse)

    async def get_account_staking_rewards(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> StakingRewardsResponse:
        """Get staking rewards for an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            timestamp: Filter by timestamp

        Returns:
            StakingRewardsResponse with staking reward information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            timestamp=timestamp,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/rewards", params)
        return self._parse_response(response, StakingRewardsResponse)

    async def get_account_tokens(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        token_id: Optional[str] = None,
    ) -> TokenRelationshipResponse:
        """Get token relationships for an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            token_id: Filter by token ID

        Returns:
            TokenRelationshipResponse with token relationship information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            token_id=token_id,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/tokens", params)
        return self._parse_response(response, TokenRelationshipResponse)

    async def get_account_pending_airdrops(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        sender_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        token_id: Optional[str] = None,
    ) -> TokenAirdropsResponse:
        """Get pending airdrops for an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            sender_id: Filter by sender ID
            serial_number: Filter by serial number
            token_id: Filter by token ID

        Returns:
            TokenAirdropsResponse with airdrop information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            sender_id=sender_id,
            serialnumber=serial_number,
            token_id=token_id,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/airdrops/pending", params)
        return self._parse_response(response, TokenAirdropsResponse)

    async def get_account_outstanding_airdrops(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        receiver_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        token_id: Optional[str] = None,
    ) -> TokenAirdropsResponse:
        """Get outstanding airdrops sent by an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            receiver_id: Filter by receiver ID
            serial_number: Filter by serial number
            token_id: Filter by token ID

        Returns:
            TokenAirdropsResponse with airdrop information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            receiver_id=receiver_id,
            serialnumber=serial_number,
            token_id=token_id,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/airdrops/outstanding", params)
        return self._parse_response(response, TokenAirdropsResponse)

    async def get_account_crypto_allowances(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        spender_id: Optional[str] = None,
    ) -> CryptoAllowancesResponse:
        """Get crypto allowances for an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            spender_id: Filter by spender ID

        Returns:
            CryptoAllowancesResponse with allowance information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            spender_id=spender_id,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/allowances/crypto", params)
        return self._parse_response(response, CryptoAllowancesResponse)

    async def get_account_token_allowances(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        spender_id: Optional[str] = None,
        token_id: Optional[str] = None,
    ) -> TokenAllowancesResponse:
        """Get token allowances for an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            spender_id: Filter by spender ID
            token_id: Filter by token ID

        Returns:
            TokenAllowancesResponse with allowance information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            spender_id=spender_id,
            token_id=token_id,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/allowances/tokens", params)
        return self._parse_response(response, TokenAllowancesResponse)

    async def get_account_nft_allowances(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        account_filter: Optional[str] = None,
        token_id: Optional[str] = None,
        owner: Optional[bool] = None,
    ) -> NftAllowancesResponse:
        """Get NFT allowances for an account.

        Args:
            account_id: Account ID, alias, or EVM address
            limit: Maximum number of results
            order: Sort order (asc/desc)
            account_filter: Filter by account ID
            token_id: Filter by token ID
            owner: Whether account is owner or spender

        Returns:
            NftAllowancesResponse with allowance information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            account_id=account_filter,
            token_id=token_id,
            owner=owner,
        )
        
        response = await self._get(f"/api/v1/accounts/{account_id}/allowances/nfts", params)
        return self._parse_response(response, NftAllowancesResponse)

    # Balance endpoints

    async def get_balances(
        self,
        account_id: Optional[str] = None,
        account_balance: Optional[str] = None,
        account_publickey: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> BalancesResponse:
        """Get account balances.

        Args:
            account_id: Filter by account ID
            account_balance: Filter by account balance
            account_publickey: Filter by account public key
            limit: Maximum number of results
            order: Sort order (asc/desc)
            timestamp: Filter by timestamp

        Returns:
            BalancesResponse with balance information
        """
        params = build_query_params(
            account_id=account_id,
            account_balance=account_balance,
            account_publickey=account_publickey,
            limit=validate_limit(limit),
            order=normalize_order(order),
            timestamp=timestamp,
        )
        
        response = await self._get("/api/v1/balances", params)
        return self._parse_response(response, BalancesResponse)

    # Block endpoints

    async def get_blocks(
        self,
        block_number: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> BlocksResponse:
        """Get blocks.

        Args:
            block_number: Filter by block number
            limit: Maximum number of results
            order: Sort order (asc/desc)
            timestamp: Filter by timestamp

        Returns:
            BlocksResponse with block information
        """
        params = build_query_params(
            block_number=block_number,
            limit=validate_limit(limit),
            order=normalize_order(order),
            timestamp=timestamp,
        )
        
        response = await self._get("/api/v1/blocks", params)
        return self._parse_response(response, BlocksResponse)

    async def get_block(self, hash_or_number: str) -> Block:
        """Get a specific block by hash or number.

        Args:
            hash_or_number: Block hash or number

        Returns:
            Block information
        """
        response = await self._get(f"/api/v1/blocks/{hash_or_number}")
        return self._parse_response(response, Block)

    # Contract endpoints

    async def call_contract(self, request: Dict[str, Any]) -> ContractCallResponse:
        """Call a smart contract function.

        Args:
            request: Contract call request parameters

        Returns:
            ContractCallResponse with the result
        """
        response = await self._post("/api/v1/contracts/call", request)
        return self._parse_response(response, ContractCallResponse)

    async def get_contracts(
        self,
        contract_id: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
    ) -> ContractsResponse:
        """Get contracts.

        Args:
            contract_id: Filter by contract ID
            limit: Maximum number of results
            order: Sort order (asc/desc)

        Returns:
            ContractsResponse with contract information
        """
        params = build_query_params(
            contract_id=contract_id,
            limit=validate_limit(limit),
            order=normalize_order(order),
        )
        
        response = await self._get("/api/v1/contracts", params)
        return self._parse_response(response, ContractsResponse)

    async def get_contract(
        self,
        contract_id: str,
        timestamp: Optional[str] = None,
    ) -> ContractResponse:
        """Get a specific contract.

        Args:
            contract_id: Contract ID or address
            timestamp: Filter by timestamp

        Returns:
            ContractResponse with contract information
        """
        params = build_query_params(timestamp=timestamp)
        
        response = await self._get(f"/api/v1/contracts/{contract_id}", params)
        return self._parse_response(response, ContractResponse)

    # Network endpoints

    async def get_network_exchange_rate(
        self,
        timestamp: Optional[str] = None,
    ) -> NetworkExchangeRateSetResponse:
        """Get network exchange rate.

        Args:
            timestamp: Filter by timestamp

        Returns:
            NetworkExchangeRateSetResponse with exchange rate information
        """
        params = build_query_params(timestamp=timestamp)
        
        response = await self._get("/api/v1/network/exchangerate", params)
        return self._parse_response(response, NetworkExchangeRateSetResponse)

    async def get_network_fees(
        self,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> NetworkFeesResponse:
        """Get network fees.

        Args:
            order: Sort order (asc/desc)
            timestamp: Filter by timestamp

        Returns:
            NetworkFeesResponse with fee information
        """
        params = build_query_params(
            order=normalize_order(order),
            timestamp=timestamp,
        )
        
        response = await self._get("/api/v1/network/fees", params)
        return self._parse_response(response, NetworkFeesResponse)

    async def get_network_nodes(
        self,
        file_id: Optional[str] = None,
        limit: Optional[int] = None,
        node_id: Optional[str] = None,
        order: Optional[str] = None,
    ) -> NetworkNodesResponse:
        """Get network nodes.

        Args:
            file_id: Filter by file ID
            limit: Maximum number of results
            node_id: Filter by node ID
            order: Sort order (asc/desc)

        Returns:
            NetworkNodesResponse with node information
        """
        params = build_query_params(
            file_id=file_id,
            limit=validate_limit(limit),
            node_id=node_id,
            order=normalize_order(order),
        )
        
        response = await self._get("/api/v1/network/nodes", params)
        return self._parse_response(response, NetworkNodesResponse)

    async def get_network_stake(self) -> NetworkStakeResponse:
        """Get network stake information.

        Returns:
            NetworkStakeResponse with stake information
        """
        response = await self._get("/api/v1/network/stake")
        return self._parse_response(response, NetworkStakeResponse)

    async def get_network_supply(
        self,
        timestamp: Optional[str] = None,
    ) -> NetworkSupplyResponse:
        """Get network supply information.

        Args:
            timestamp: Filter by timestamp

        Returns:
            NetworkSupplyResponse with supply information
        """
        params = build_query_params(timestamp=timestamp)
        
        response = await self._get("/api/v1/network/supply", params)
        return self._parse_response(response, NetworkSupplyResponse)

    # Schedule endpoints

    async def get_schedules(
        self,
        account_id: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        schedule_id: Optional[str] = None,
    ) -> SchedulesResponse:
        """Get schedules.

        Args:
            account_id: Filter by account ID
            limit: Maximum number of results
            order: Sort order (asc/desc)
            schedule_id: Filter by schedule ID

        Returns:
            SchedulesResponse with schedule information
        """
        params = build_query_params(
            account_id=account_id,
            limit=validate_limit(limit),
            order=normalize_order(order),
            schedule_id=schedule_id,
        )
        
        response = await self._get("/api/v1/schedules", params)
        return self._parse_response(response, SchedulesResponse)

    async def get_schedule(self, schedule_id: str) -> Schedule:
        """Get a specific schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            Schedule information
        """
        response = await self._get(f"/api/v1/schedules/{schedule_id}")
        return self._parse_response(response, Schedule)

    # Transaction endpoints

    async def get_transactions(
        self,
        account_id: str,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
        transaction_type: Optional[str] = None,
        result: Optional[str] = None,
        type: Optional[str] = None,
    ) -> TransactionsResponse:
        """Get all transactions of an account with manual timestamp-based pagination."""
        params = build_query_params(
            account_id=account_id,
            limit=limit,
            order=normalize_order(order),
            timestamp=timestamp,
            transactiontype=transaction_type,
            result=result,
            type=type,
        )
        # Get first page
        response = await self._get(f"/api/v1/transactions", params)
        all_transactions = response.get('transactions', [])
        
        # Manual pagination using consensus_timestamp
        start_time = timer()
        timeout_seconds = self.request_timeout
        page_count = 1
        last_used_timestamp = None  # Track the last timestamp we used

        
        # Continue while there are transactions in the response
        while response.get('links', {}).get('next'):
            # Check timeout
            elapsed_time = timer() - start_time
            if elapsed_time >= timeout_seconds:
                logger.warning(f"Pagination timeout reached after {elapsed_time:.2f} seconds")
                break
            
            current_transaction_count = len(response.get('transactions', []))
            
            if current_transaction_count == FULL_PAGE_SIZE:
                # Full page - use last transaction's timestamp
                last_transaction = response['transactions'][-1]
                last_timestamp = last_transaction['consensus_timestamp']
                next_timestamp = f"lt:{last_timestamp}"
                logger.info(f"Page {page_count}: Full page ({current_transaction_count} results), using timestamp: {last_timestamp}")
            else:
                if last_used_timestamp is None:
                    # First time - use current time as fallback
                    current_epoch = time.time()
                    fallback_seconds = FALLBACK_DAYS * SECONDS_PER_DAY
                    fallback_epoch = current_epoch - fallback_seconds
                    logger.info(f"Page {page_count}: First partial page, using current time - {FALLBACK_DAYS} days: {fallback_epoch}")
                else:
                    # Subsequent times - use last used timestamp - 60 days
                    last_timestamp = float(last_used_timestamp)
                    fallback_seconds = FALLBACK_DAYS * SECONDS_PER_DAY
                    fallback_epoch = last_timestamp - fallback_seconds
                    logger.info(f"Page {page_count}: Subsequent partial page, using last timestamp - {FALLBACK_DAYS} days: {fallback_epoch}")
                
                fallback_timestamp = f"{fallback_epoch:.9f}"
                next_timestamp = f"lt:{fallback_timestamp}"
                last_used_timestamp = fallback_timestamp  # Update our tracker
                logger.info(f"Page {page_count}: Partial page ({current_transaction_count} results), using {FALLBACK_DAYS}-day fallback: {fallback_timestamp}")
            
            # Construct next page parameters
            next_params = params.copy()
            next_params['timestamp'] = next_timestamp
            
            # Get next page
            next_response = await self._get(f"/api/v1/transactions", next_params)
            next_transactions = next_response.get('transactions', [])
            
            # Append transactions from this page
            all_transactions.extend(next_transactions)
            # Update response for next iteration
            response = next_response
            page_count += 1
        
        # Create final response with all transactions
        final_response = response.copy()
        final_response['transactions'] = all_transactions
        
        logger.info(f"Total transactions collected: {len(all_transactions)} from {page_count} pages")
        return self._parse_response(final_response, TransactionsResponse)

    async def get_transaction(
        self,
        transaction_id: str,
        nonce: Optional[int] = None,
        scheduled: Optional[bool] = None,
    ) -> TransactionByIdResponse:
        """Get a specific transaction.

        Args:
            transaction_id: Transaction ID
            nonce: Transaction nonce
            scheduled: Whether transaction is scheduled

        Returns:
            TransactionByIdResponse with transaction information
        """
        params = build_query_params(
            nonce=nonce,
            scheduled=scheduled,
        )
        
        response = await self._get(f"/api/v1/transactions/{transaction_id}", params)
        return self._parse_response(response, TransactionByIdResponse)

    # Topic endpoints

    async def get_topic(self, topic_id: str) -> Topic:
        """Get a specific topic.

        Args:
            topic_id: Topic ID

        Returns:
            Topic information
        """
        response = await self._get(f"/api/v1/topics/{topic_id}")
        return self._parse_response(response, Topic)

    async def get_topic_messages(
        self,
        topic_id: str,
        encoding: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        sequencenumber: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> TopicMessagesResponse:
        """Get topic messages.

        Args:
            topic_id: Topic ID
            encoding: Message encoding
            limit: Maximum number of results
            order: Sort order (asc/desc)
            sequencenumber: Filter by sequence number
            timestamp: Filter by timestamp

        Returns:
            TopicMessagesResponse with message information
        """
        params = build_query_params(
            encoding=encoding,
            limit=validate_limit(limit),
            order=normalize_order(order),
            sequencenumber=sequencenumber,
            timestamp=timestamp,
        )
        
        response = await self._get(f"/api/v1/topics/{topic_id}/messages", params)
        return self._parse_response(response, TopicMessagesResponse)

    async def get_topic_message(
        self,
        topic_id: str,
        sequence_number: int,
    ) -> TopicMessage:
        """Get a specific topic message.

        Args:
            topic_id: Topic ID
            sequence_number: Message sequence number

        Returns:
            TopicMessage information
        """
        response = await self._get(f"/api/v1/topics/{topic_id}/messages/{sequence_number}")
        return self._parse_response(response, TopicMessage)

    async def get_topic_message_by_timestamp(self, timestamp: str) -> TopicMessage:
        """Get a topic message by timestamp.

        Args:
            timestamp: Message timestamp

        Returns:
            TopicMessage information
        """
        response = await self._get(f"/api/v1/topics/messages/{timestamp}")
        return self._parse_response(response, TopicMessage)

    # Token endpoints

    async def get_tokens(
        self,
        account_id: Optional[str] = None,
        limit: Optional[int] = None,
        name: Optional[str] = None,
        order: Optional[str] = None,
        publickey: Optional[str] = None,
        token_id: Optional[str] = None,
        type: Optional[List[str]] = None,
    ) -> TokensResponse:
        """Get tokens.

        Args:
            account_id: Filter by account ID
            limit: Maximum number of results
            name: Filter by token name
            order: Sort order (asc/desc)
            publickey: Filter by public key
            token_id: Filter by token ID
            type: Filter by token type

        Returns:
            TokensResponse with token information
        """
        params = build_query_params(
            account_id=account_id,
            limit=validate_limit(limit),
            name=name,
            order=normalize_order(order),
            publickey=publickey,
            token_id=token_id,
            type=type,
        )
        
        response = await self._get("/api/v1/tokens", params)
        return self._parse_response(response, TokensResponse)

    async def get_token(
        self,
        token_id: str,
        timestamp: Optional[str] = None,
    ) -> TokenInfo:
        """Get a specific token.

        Args:
            token_id: Token ID
            timestamp: Filter by timestamp

        Returns:
            TokenInfo with token information
        """
        params = build_query_params(timestamp=timestamp)
        
        response = await self._get(f"/api/v1/tokens/{token_id}", params)
        return self._parse_response(response, TokenInfo)

    async def get_token_balances(
        self,
        token_id: str,
        account_balance: Optional[str] = None,
        account_id: Optional[str] = None,
        account_publickey: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> TokenBalancesResponse:
        """Get token balances.

        Args:
            token_id: Token ID
            account_balance: Filter by account balance
            account_id: Filter by account ID
            account_publickey: Filter by account public key
            limit: Maximum number of results
            order: Sort order (asc/desc)
            timestamp: Filter by timestamp

        Returns:
            TokenBalancesResponse with balance information
        """
        params = build_query_params(
            account_balance=account_balance,
            account_id=account_id,
            account_publickey=account_publickey,
            limit=validate_limit(limit),
            order=normalize_order(order),
            timestamp=timestamp,
        )
        
        response = await self._get(f"/api/v1/tokens/{token_id}/balances", params)
        return self._parse_response(response, TokenBalancesResponse)

    async def get_token_nfts(
        self,
        token_id: str,
        account_id: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        serial_number: Optional[str] = None,
    ) -> NftsResponse:
        """Get NFTs for a token.

        Args:
            token_id: Token ID
            account_id: Filter by account ID
            limit: Maximum number of results
            order: Sort order (asc/desc)
            serial_number: Filter by serial number

        Returns:
            NftsResponse with NFT information
        """
        params = build_query_params(
            account_id=account_id,
            limit=validate_limit(limit),
            order=normalize_order(order),
            serialnumber=serial_number,
        )
        
        response = await self._get(f"/api/v1/tokens/{token_id}/nfts", params)
        return self._parse_response(response, NftsResponse)

    async def get_nft(self, token_id: str, serial_number: int) -> Nft:
        """Get a specific NFT.

        Args:
            token_id: Token ID
            serial_number: NFT serial number

        Returns:
            Nft information
        """
        response = await self._get(f"/api/v1/tokens/{token_id}/nfts/{serial_number}")
        return self._parse_response(response, Nft)

    async def get_nft_transaction_history(
        self,
        token_id: str,
        serial_number: int,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> NftTransactionHistory:
        """Get NFT transaction history.

        Args:
            token_id: Token ID
            serial_number: NFT serial number
            limit: Maximum number of results
            order: Sort order (asc/desc)
            timestamp: Filter by timestamp

        Returns:
            NftTransactionHistory with transaction information
        """
        params = build_query_params(
            limit=validate_limit(limit),
            order=normalize_order(order),
            timestamp=timestamp,
        )
        
        response = await self._get(f"/api/v1/tokens/{token_id}/nfts/{serial_number}/transactions", params)
        return self._parse_response(response, NftTransactionHistory)

    # Pagination utilities

    async def get_accounts_paginated(
        self,
        limit: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[AccountsResponse]:
        """Get accounts with automatic pagination.

        Args:
            limit: Page size
            **kwargs: Additional query parameters

        Yields:
            AccountsResponse objects for each page
        """
        response = await self.get_accounts(limit=limit, **kwargs)
        yield response
        
        while response.links.next:
            next_link = extract_next_link(response.links.__dict__)
            if next_link:
                # Parse query parameters from next link
                query_params = dict(parse_qs(next_link))
                # Convert list values to single values and filter parameters
                next_params = {}
                for key, value in query_params.items():
                    if isinstance(value, list) and len(value) == 1:
                        next_params[key] = value[0]
                    elif isinstance(value, list) and len(value) > 1:
                        next_params[key] = value
                
                response = await self.get_accounts(**next_params)
                yield response
            else:
                break

    async def get_transactions_paginated(
        self,
        limit: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[TransactionsResponse]:
        """Get transactions with automatic pagination.

        Args:
            limit: Page size
            **kwargs: Additional query parameters

        Yields:
            TransactionsResponse objects for each page
        """
        response = await self.get_transactions(limit=limit, **kwargs)
        yield response
        
        while response.links.next:
            next_link = extract_next_link(response.links.__dict__)
            if next_link:
                # Parse query parameters from next link
                query_params = dict(parse_qs(next_link))
                # Convert list values to single values and filter parameters
                next_params = {}
                for key, value in query_params.items():
                    if isinstance(value, list) and len(value) == 1:
                        next_params[key] = value[0]
                    elif isinstance(value, list) and len(value) > 1:
                        next_params[key] = value
                
                response = await self.get_transactions(**next_params)
                yield response
            else:
                break