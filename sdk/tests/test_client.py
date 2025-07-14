"""Tests for the Hiero Mirror Node SDK."""

import pytest
from unittest.mock import Mock, patch
import httpx
from hiero_mirror import MirrorNodeClient, AsyncMirrorNodeClient
from hiero_mirror.exceptions import NotFoundError, BadRequestError


class TestMirrorNodeClient:
    """Test the synchronous client."""
    
    def test_client_initialization(self):
        """Test client initialization."""
        client = MirrorNodeClient("https://testnet.mirrornode.hedera.com")
        assert client.base_url == "https://testnet.mirrornode.hedera.com"
        assert client.timeout == 30.0
        client.close()
    
    def test_for_testnet(self):
        """Test testnet client factory."""
        client = MirrorNodeClient.for_testnet()
        assert "testnet" in client.base_url
        client.close()
    
    def test_for_mainnet(self):
        """Test mainnet client factory."""
        client = MirrorNodeClient.for_mainnet()
        assert "mainnet" in client.base_url
        client.close()
    
    def test_for_previewnet(self):
        """Test previewnet client factory."""
        client = MirrorNodeClient.for_previewnet()
        assert "previewnet" in client.base_url
        client.close()
    
    @patch('httpx.Client.request')
    def test_get_accounts(self, mock_request):
        """Test get_accounts method."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "accounts": [
                {
                    "account": "0.0.2",
                    "balance": {
                        "balance": 1000000000,
                        "timestamp": "1234567890.000000000",
                        "tokens": []
                    },
                    "alias": None,
                    "auto_renew_period": None,
                    "created_timestamp": "1234567890.000000000",
                    "decline_reward": False,
                    "deleted": False,
                    "ethereum_nonce": 0,
                    "evm_address": None,
                    "expiry_timestamp": None,
                    "key": None,
                    "max_automatic_token_associations": None,
                    "memo": "",
                    "pending_reward": 0,
                    "receiver_sig_required": False,
                    "staked_account_id": None,
                    "staked_node_id": None,
                    "stake_period_start": None
                }
            ],
            "links": {
                "next": None
            }
        }
        mock_request.return_value = mock_response
        
        client = MirrorNodeClient.for_testnet()
        try:
            accounts = client.get_accounts(limit=1)
            assert len(accounts.accounts) == 1
            assert accounts.accounts[0].account == "0.0.2"
        finally:
            client.close()
    
    @patch('httpx.Client.request')
    def test_get_account_not_found(self, mock_request):
        """Test get_account with not found error."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "_status": {
                "messages": [
                    {"message": "Account not found"}
                ]
            }
        }
        mock_request.return_value = mock_response
        
        client = MirrorNodeClient.for_testnet()
        try:
            with pytest.raises(NotFoundError) as exc_info:
                client.get_account("0.0.999999999")
            assert "Account not found" in str(exc_info.value)
        finally:
            client.close()
    
    @patch('httpx.Client.request')
    def test_get_transactions(self, mock_request):
        """Test get_transactions method."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "bytes": None,
                    "charged_tx_fee": 1000000,
                    "consensus_timestamp": "1234567890.000000000",
                    "entity_id": "0.0.2",
                    "max_fee": "100000000",
                    "memo_base64": None,
                    "name": "CRYPTOTRANSFER",
                    "nft_transfers": [],
                    "node": "0.0.3",
                    "nonce": 0,
                    "parent_consensus_timestamp": None,
                    "result": "SUCCESS",
                    "scheduled": False,
                    "staking_reward_transfers": [],
                    "token_transfers": [],
                    "transaction_hash": "abcd1234",
                    "transaction_id": "0.0.2-1234567890-000000000",
                    "transfers": [],
                    "valid_duration_seconds": "120",
                    "valid_start_timestamp": "1234567889.000000000"
                }
            ],
            "links": {
                "next": None
            }
        }
        mock_request.return_value = mock_response
        
        client = MirrorNodeClient.for_testnet()
        try:
            transactions = client.get_transactions(limit=1)
            assert len(transactions.transactions) == 1
            assert transactions.transactions[0].name == "CRYPTOTRANSFER"
        finally:
            client.close()
    
    def test_context_manager(self):
        """Test client as context manager."""
        with MirrorNodeClient.for_testnet() as client:
            assert client.base_url is not None


class TestAsyncMirrorNodeClient:
    """Test the asynchronous client."""
    
    def test_client_initialization(self):
        """Test async client initialization."""
        client = AsyncMirrorNodeClient("https://testnet.mirrornode.hedera.com")
        assert client.base_url == "https://testnet.mirrornode.hedera.com"
        assert client.timeout == 30.0
    
    def test_for_testnet(self):
        """Test testnet async client factory."""
        client = AsyncMirrorNodeClient.for_testnet()
        assert "testnet" in client.base_url
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.request')
    async def test_get_accounts(self, mock_request):
        """Test async get_accounts method."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "accounts": [
                {
                    "account": "0.0.2",
                    "balance": {
                        "balance": 1000000000,
                        "timestamp": "1234567890.000000000",
                        "tokens": []
                    },
                    "alias": None,
                    "auto_renew_period": None,
                    "created_timestamp": "1234567890.000000000",
                    "decline_reward": False,
                    "deleted": False,
                    "ethereum_nonce": 0,
                    "evm_address": None,
                    "expiry_timestamp": None,
                    "key": None,
                    "max_automatic_token_associations": None,
                    "memo": "",
                    "pending_reward": 0,
                    "receiver_sig_required": False,
                    "staked_account_id": None,
                    "staked_node_id": None,
                    "stake_period_start": None
                }
            ],
            "links": {
                "next": None
            }
        }
        mock_request.return_value = mock_response
        
        async with AsyncMirrorNodeClient.for_testnet() as client:
            accounts = await client.get_accounts(limit=1)
            assert len(accounts.accounts) == 1
            assert accounts.accounts[0].account == "0.0.2"
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async client as context manager."""
        async with AsyncMirrorNodeClient.for_testnet() as client:
            assert client.base_url is not None