#!/usr/bin/env python3
"""Advanced usage examples for Hiero Mirror Node SDK."""

import asyncio
from datetime import datetime, timedelta
from hiero_mirror import MirrorNodeClient, AsyncMirrorNodeClient
from hiero_mirror.utils import to_timestamp, from_timestamp, format_hbar_balance


def timestamp_filtering_example():
    """Example of timestamp filtering."""
    print("=== Timestamp Filtering Example ===")
    
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Get current time and 1 hour ago
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        print(f"Filtering transactions from {one_hour_ago} to {now}")
        
        # Convert to Hiero timestamp format
        timestamp_filter = f"gte:{to_timestamp(one_hour_ago)}"
        
        # Get transactions from the last hour
        transactions = client.get_transactions(
            timestamp=timestamp_filter,
            limit=10,
            order="desc"
        )
        
        print(f"Found {len(transactions.transactions)} transactions in the last hour")
        
        for tx in transactions.transactions:
            # Convert timestamp back to datetime for display
            tx_time = from_timestamp(tx.consensus_timestamp)
            print(f"  - {tx.transaction_id}: {tx.name} at {tx_time}")
        
        # Get account info at a specific timestamp
        print("\n2. Getting account info at specific timestamp...")
        account_timestamp = to_timestamp(one_hour_ago)
        account = client.get_account("0.0.2", timestamp=account_timestamp)
        
        print(f"Account 0.0.2 at {one_hour_ago}:")
        print(f"  Balance: {format_hbar_balance(account.balance.balance if account.balance else 0)} HBAR")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        client.close()


def token_analysis_example():
    """Example of token analysis."""
    print("\n=== Token Analysis Example ===")
    
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Get tokens
        print("1. Getting tokens...")
        tokens = client.get_tokens(limit=10)
        print(f"Found {len(tokens.tokens)} tokens")
        
        # Analyze each token
        for token in tokens.tokens[:3]:  # Limit to first 3 for demo
            print(f"\nAnalyzing token {token.token_id} ({token.name}):")
            
            # Get token details
            token_info = client.get_token(token.token_id)
            print(f"  Type: {token_info.type}")
            print(f"  Supply: {token_info.total_supply}")
            print(f"  Decimals: {token_info.decimals}")
            print(f"  Treasury: {token_info.treasury_account_id}")
            
            # Get token balances
            balances = client.get_token_balances(token.token_id, limit=5)
            print(f"  Holders: {len(balances.balances)}")
            
            total_distributed = sum(balance.balance for balance in balances.balances)
            print(f"  Total distributed (sample): {total_distributed}")
            
            # If it's an NFT token, get some NFTs
            if token_info.type == "NON_FUNGIBLE_UNIQUE":
                nfts = client.get_token_nfts(token.token_id, limit=3)
                print(f"  NFTs: {len(nfts.nfts)}")
                
                for nft in nfts.nfts:
                    print(f"    - Serial {nft.serial_number}: owner {nft.account_id}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        client.close()


def account_analysis_example():
    """Example of account analysis."""
    print("\n=== Account Analysis Example ===")
    
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Get a specific account
        account_id = "0.0.2"
        print(f"Analyzing account {account_id}...")
        
        # Get account info with transactions
        account = client.get_account(account_id, transactions=True, limit=10)
        
        print(f"Account {account_id}:")
        print(f"  Balance: {format_hbar_balance(account.balance.balance if account.balance else 0)} HBAR")
        print(f"  Memo: {account.memo or 'None'}")
        print(f"  Auto-renew: {account.auto_renew_period or 'None'}")
        print(f"  Recent transactions: {len(account.transactions)}")
        
        # Analyze transaction types
        tx_types = {}
        for tx in account.transactions:
            tx_type = tx.name
            tx_types[tx_type] = tx_types.get(tx_type, 0) + 1
        
        print("\n  Transaction types:")
        for tx_type, count in sorted(tx_types.items()):
            print(f"    {tx_type}: {count}")
        
        # Get account tokens
        print("\n2. Account tokens...")
        tokens = client.get_account_tokens(account_id, limit=10)
        print(f"  Associated tokens: {len(tokens.tokens)}")
        
        for token_rel in tokens.tokens:
            balance_str = format_hbar_balance(token_rel.balance) if token_rel.decimals == 8 else str(token_rel.balance)
            print(f"    {token_rel.token_id}: {balance_str} (decimals: {token_rel.decimals})")
        
        # Get account NFTs
        print("\n3. Account NFTs...")
        nfts = client.get_account_nfts(account_id, limit=5)
        print(f"  NFTs owned: {len(nfts.nfts)}")
        
        for nft in nfts.nfts:
            print(f"    Token {nft.token_id}, Serial {nft.serial_number}")
        
        # Get account allowances
        print("\n4. Account allowances...")
        
        # Crypto allowances
        crypto_allowances = client.get_account_crypto_allowances(account_id, limit=5)
        print(f"  Crypto allowances: {len(crypto_allowances.allowances)}")
        
        # Token allowances
        token_allowances = client.get_account_token_allowances(account_id, limit=5)
        print(f"  Token allowances: {len(token_allowances.allowances)}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        client.close()


async def concurrent_data_fetching():
    """Example of concurrent data fetching."""
    print("\n=== Concurrent Data Fetching Example ===")
    
    async with AsyncMirrorNodeClient.for_testnet() as client:
        try:
            # Define multiple data fetching tasks
            tasks = [
                client.get_accounts(limit=5),
                client.get_transactions(limit=5),
                client.get_tokens(limit=5),
                client.get_network_exchange_rate(),
                client.get_network_supply(),
                client.get_blocks(limit=3),
            ]
            
            # Execute all tasks concurrently
            print("Fetching data concurrently...")
            start_time = datetime.now()
            
            results = await asyncio.gather(*tasks)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Process results
            accounts, transactions, tokens, exchange_rate, supply, blocks = results
            
            print(f"Fetched data in {duration:.2f} seconds:")
            print(f"  - {len(accounts.accounts)} accounts")
            print(f"  - {len(transactions.transactions)} transactions")
            print(f"  - {len(tokens.tokens)} tokens")
            print(f"  - Exchange rate: {exchange_rate.current_rate.hbar_equivalent} HBAR = {exchange_rate.current_rate.cent_equivalent} cents")
            print(f"  - Total supply: {supply.total_supply} tinybars")
            print(f"  - {len(blocks.blocks)} blocks")
            
        except Exception as e:
            print(f"Error: {e}")


def network_monitoring_example():
    """Example of network monitoring."""
    print("\n=== Network Monitoring Example ===")
    
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Get network information
        print("1. Network overview...")
        
        # Exchange rate
        exchange_rate = client.get_network_exchange_rate()
        print(f"Exchange rate: {exchange_rate.current_rate.hbar_equivalent} HBAR = {exchange_rate.current_rate.cent_equivalent} cents")
        
        # Supply
        supply = client.get_network_supply()
        total_supply_hbar = int(supply.total_supply) / 100_000_000  # Convert to HBAR
        released_supply_hbar = int(supply.released_supply) / 100_000_000
        print(f"Total supply: {total_supply_hbar:,.0f} HBAR")
        print(f"Released supply: {released_supply_hbar:,.0f} HBAR")
        
        # Network fees
        fees = client.get_network_fees()
        print(f"\nNetwork fees ({len(fees.fees)} transaction types):")
        for fee in fees.fees:
            print(f"  {fee.transaction_type}: {fee.gas} gas")
        
        # Network nodes
        nodes = client.get_network_nodes(limit=5)
        print(f"\nNetwork nodes: {len(nodes.nodes)}")
        for node in nodes.nodes:
            print(f"  Node {node.node_id}: {node.node_account_id}")
        
        # Network stake
        stake = client.get_network_stake()
        print(f"\nNetwork stake:")
        print(f"  Total stake: {stake.stake_total} tinybars")
        print(f"  Staking reward rate: {stake.staking_reward_rate} tinybars/period")
        
        # Recent blocks
        blocks = client.get_blocks(limit=3, order="desc")
        print(f"\nRecent blocks:")
        for block in blocks.blocks:
            print(f"  Block {block.number}: {block.count} transactions")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        client.close()


def error_handling_example():
    """Example of error handling."""
    print("\n=== Error Handling Example ===")
    
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Example 1: Handle not found error
        try:
            account = client.get_account("0.0.999999999")
            print(f"Found account: {account.account}")
        except Exception as e:
            print(f"Expected error - Account not found: {e}")
        
        # Example 2: Handle invalid parameters
        try:
            accounts = client.get_accounts(limit=1000)  # Too large
            print(f"Found {len(accounts.accounts)} accounts")
        except Exception as e:
            print(f"Expected error - Invalid limit: {e}")
        
        # Example 3: Handle invalid entity ID
        try:
            account = client.get_account("invalid-id")
            print(f"Found account: {account.account}")
        except Exception as e:
            print(f"Expected error - Invalid entity ID: {e}")
        
        print("\nError handling completed successfully!")
        
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    finally:
        client.close()


def main():
    """Main function to run all advanced examples."""
    print("Hiero Mirror Node SDK Advanced Examples")
    print("=" * 60)
    
    # Run examples
    timestamp_filtering_example()
    token_analysis_example()
    account_analysis_example()
    asyncio.run(concurrent_data_fetching())
    network_monitoring_example()
    error_handling_example()
    
    print("\n" + "=" * 60)
    print("All advanced examples completed!")


if __name__ == "__main__":
    main()