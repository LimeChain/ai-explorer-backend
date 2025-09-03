# Hiero Mirror Node Python SDK

A Python SDK for interacting with the Hiero Mirror Node REST API.

## Features

- **Complete API Coverage** - All Mirror Node REST endpoints
- **Type Safety** - Full type hints with Pydantic models
- **Async Support** - Both synchronous and asynchronous clients
- **Pagination** - Easy handling of paginated responses
- **Network Presets** - Pre-configured for mainnet, testnet, and previewnet
- **Hiero Utilities** - Helper functions for entity IDs, timestamps, and more
- **Error Handling** - Structured exception handling
- **Retry Logic** - Built-in retry mechanisms with exponential backoff

## Installation

```bash
pip install hiero-mirror-node-sdk
```

## Quick Start

### Synchronous Client

```python
from hiero_mirror import MirrorNodeClient

# Initialize client for testnet
client = MirrorNodeClient.for_testnet()

# Get accounts
accounts = client.get_accounts(limit=10)
print(f"Found {len(accounts.accounts)} accounts")

# Get specific account
account = client.get_account("0.0.1001")
print(f"Account balance: {account.balance.balance} tinybars")

# Get account tokens
tokens = client.get_account_tokens("0.0.1001")
for token in tokens.tokens:
    print(f"Token {token.token_id}: {token.balance}")
```

### Asynchronous Client

```python
import asyncio
from hiero_mirror import AsyncMirrorNodeClient

async def main():
    # Initialize async client
    client = AsyncMirrorNodeClient.for_testnet()
    
    # Get accounts
    accounts = await client.get_accounts(limit=10)
    print(f"Found {len(accounts.accounts)} accounts")
    
    # Get specific account
    account = await client.get_account("0.0.1001")
    print(f"Account balance: {account.balance.balance} tinybars")
    
    # Close client
    await client.close()

asyncio.run(main())
```

## Network Configuration

```python
from hiero_mirror import MirrorNodeClient

# Pre-configured networks
mainnet = MirrorNodeClient.for_mainnet()
testnet = MirrorNodeClient.for_testnet()
previewnet = MirrorNodeClient.for_previewnet()

# Custom network
custom = MirrorNodeClient(base_url="https://custom.mirror.node")
```

## Advanced Usage

### Pagination

```python
# Manual pagination
accounts = client.get_accounts(limit=25)
while accounts.links.next:
    next_accounts = client.get_accounts_from_link(accounts.links.next)
    accounts.accounts.extend(next_accounts.accounts)
    accounts = next_accounts

# Automatic pagination
all_accounts = []
for accounts_page in client.get_accounts_paginated(limit=100):
    all_accounts.extend(accounts_page.accounts)
```

### Error Handling

```python
from hiero_mirror import MirrorNodeClient, MirrorNodeException, NotFoundError

client = MirrorNodeClient.for_testnet()

try:
    account = client.get_account("0.0.999999999")
except NotFoundError as e:
    print(f"Account not found: {e}")
except MirrorNodeException as e:
    print(f"API error: {e.status_code} - {e.message}")
```

### Filtering and Timestamps

```python
from datetime import datetime
from hiero_mirror import MirrorNodeClient
from hiero_mirror.utils import to_timestamp

client = MirrorNodeClient.for_testnet()

# Get transactions with timestamp filter
timestamp = to_timestamp(datetime.now())
transactions = client.get_transactions(
    account_id="0.0.1001",
    timestamp=f"lt:{timestamp}",
    limit=50
)

# Get account balance at specific time
account = client.get_account("0.0.1001", timestamp=timestamp)
```

### Contract Calls

```python
# Call smart contract function
result = client.call_contract({
    "to": "0x1234567890abcdef1234567890abcdef12345678",
    "data": "0x06fdde03",  # name() function
    "estimate": False
})

print(f"Contract result: {result.result}")
```

## API Reference

### Main Client Classes

- `MirrorNodeClient` - Synchronous client
- `AsyncMirrorNodeClient` - Asynchronous client

### Account Operations

```python
# Get all accounts
accounts = client.get_accounts(limit=25, order="desc")

# Get specific account
account = client.get_account("0.0.1001", transactions=True)

# Get account NFTs
nfts = client.get_account_nfts("0.0.1001", token_id="0.0.2000")

# Get account tokens
tokens = client.get_account_tokens("0.0.1001")

# Get account allowances
crypto_allowances = client.get_account_crypto_allowances("0.0.1001")
token_allowances = client.get_account_token_allowances("0.0.1001")
nft_allowances = client.get_account_nft_allowances("0.0.1001")

# Get account airdrops
pending_airdrops = client.get_account_pending_airdrops("0.0.1001")
outstanding_airdrops = client.get_account_outstanding_airdrops("0.0.1001")

# Get staking rewards
rewards = client.get_account_staking_rewards("0.0.1001")
```

### Transaction Operations

```python
# Get all transactions
transactions = client.get_transactions(limit=25, order="desc")

# Get specific transaction
transaction = client.get_transaction("0.0.1001-1234567890-000000000")

# Get transactions by account
transactions = client.get_transactions(account_id="0.0.1001")
```

### Token Operations

```python
# Get all tokens
tokens = client.get_tokens(limit=25)

# Get specific token
token = client.get_token("0.0.2000")

# Get token balances
balances = client.get_token_balances("0.0.2000")

# Get token NFTs
nfts = client.get_token_nfts("0.0.2000")

# Get specific NFT
nft = client.get_nft("0.0.2000", 1)

# Get NFT transaction history
history = client.get_nft_transaction_history("0.0.2000", 1)
```

### Contract Operations

```python
# Get all contracts
contracts = client.get_contracts(limit=25)

# Get specific contract
contract = client.get_contract("0.0.3000")

# Get contract results
results = client.get_contract_results("0.0.3000")

# Get contract logs
logs = client.get_contract_logs("0.0.3000")

# Get contract state
state = client.get_contract_state("0.0.3000")

# Call contract
result = client.call_contract({
    "to": "0x1234567890abcdef1234567890abcdef12345678",
    "data": "0x06fdde03"
})
```

### Network Operations

```python
# Get network exchange rate
exchange_rate = client.get_network_exchange_rate()

# Get network fees
fees = client.get_network_fees()

# Get network nodes
nodes = client.get_network_nodes()

# Get network stake
stake = client.get_network_stake()

# Get network supply
supply = client.get_network_supply()
```

### Topic Operations

```python
# Get topic info
topic = client.get_topic("0.0.4000")

# Get topic messages
messages = client.get_topic_messages("0.0.4000")

# Get specific topic message
message = client.get_topic_message("0.0.4000", 1)
```

### Block Operations

```python
# Get blocks
blocks = client.get_blocks(limit=25)

# Get specific block
block = client.get_block("0x1234567890abcdef")  # by hash
block = client.get_block("12345")  # by number
```

### Schedule Operations

```python
# Get schedules
schedules = client.get_schedules(limit=25)

# Get specific schedule
schedule = client.get_schedule("0.0.5000")
```

## Utility Functions

```python
from hiero_mirror.utils import (
    parse_entity_id,
    format_entity_id,
    to_timestamp,
    from_timestamp,
    parse_timestamp,
    format_balance,
    validate_entity_id,
    is_valid_evm_address
)

# Entity ID utilities
entity_id = parse_entity_id("0.0.1001")  # Returns EntityId(shard=0, realm=0, num=1001)
formatted = format_entity_id(entity_id)  # Returns "0.0.1001"

# Timestamp utilities
timestamp = to_timestamp(datetime.now())
dt = from_timestamp("1234567890.000000000")

# Balance formatting
balance_str = format_balance(1000000, decimals=8)  # "0.01000000"

# Validation
is_valid = validate_entity_id("0.0.1001")  # True
is_valid_addr = is_valid_evm_address("0x1234567890abcdef1234567890abcdef12345678")  # True
```

## Configuration

```python
from hiero_mirror import MirrorNodeClient

client = MirrorNodeClient(
    base_url="https://testnet.mirrornode.hedera.com",
    timeout=30.0,
    retry_attempts=3,
    retry_delay=1.0,
    retry_backoff=2.0,
    user_agent="MyApp/1.0",
    headers={"X-Custom-Header": "value"}
)
```

## Development

### Setup

```bash
git clone https://github.com/hiero-ledger/hiero-mirror-node.git
cd hiero-mirror-node/sdk/python
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black hiero_mirror/

# Lint code
flake8 hiero_mirror/

# Type checking
mypy hiero_mirror/
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE) for details.