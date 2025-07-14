#!/usr/bin/env python3
"""Basic usage example for Hiero Mirror Node SDK."""

import asyncio
from hiero_mirror import MirrorNodeClient, AsyncMirrorNodeClient


def sync_example():
    """Example using the synchronous client."""
    print("=== Synchronous Client Example ===")
    
    # Initialize client for testnet
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Get accounts
        print("\n1. Getting accounts...")
        accounts = client.get_accounts(limit=5)
        print(f"Found {len(accounts.accounts)} accounts")
        
        for account in accounts.accounts:
            print(f"  - {account.account}: {account.balance.balance if account.balance else 'N/A'} tinybars")
        
        # Get specific account
        print("\n2. Getting specific account...")
        account = client.get_account("0.0.2")
        print(f"Account 0.0.2:")
        print(f"  Balance: {account.balance.balance if account.balance else 'N/A'} tinybars")
        print(f"  Memo: {account.memo or 'None'}")
        print(f"  Auto-renew period: {account.auto_renew_period or 'None'}")
        
        # Get transactions
        print("\n3. Getting recent transactions...")
        transactions = client.get_transactions(limit=3, order="desc")
        print(f"Found {len(transactions.transactions)} transactions")
        
        for tx in transactions.transactions:
            print(f"  - {tx.transaction_id}: {tx.name} ({tx.result})")
        
        # Get tokens
        print("\n4. Getting tokens...")
        tokens = client.get_tokens(limit=3)
        print(f"Found {len(tokens.tokens)} tokens")
        
        for token in tokens.tokens:
            print(f"  - {token.token_id}: {token.name} ({token.symbol})")
        
        # Get network information
        print("\n5. Getting network information...")
        exchange_rate = client.get_network_exchange_rate()
        print(f"Exchange rate: {exchange_rate.current_rate.hbar_equivalent} HBAR = {exchange_rate.current_rate.cent_equivalent} cents")
        
        supply = client.get_network_supply()
        print(f"Total supply: {supply.total_supply} tinybars")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        client.close()


async def async_example():
    """Example using the asynchronous client."""
    print("\n=== Asynchronous Client Example ===")
    
    # Initialize async client for testnet
    async with AsyncMirrorNodeClient.for_testnet() as client:
        try:
            # Get accounts
            print("\n1. Getting accounts...")
            accounts = await client.get_accounts(limit=5)
            print(f"Found {len(accounts.accounts)} accounts")
            
            for account in accounts.accounts:
                print(f"  - {account.account}: {account.balance.balance if account.balance else 'N/A'} tinybars")
            
            # Get specific account
            print("\n2. Getting specific account...")
            account = await client.get_account("0.0.2")
            print(f"Account 0.0.2:")
            print(f"  Balance: {account.balance.balance if account.balance else 'N/A'} tinybars")
            print(f"  Memo: {account.memo or 'None'}")
            
            # Get transactions concurrently
            print("\n3. Getting data concurrently...")
            tasks = [
                client.get_transactions(limit=3, order="desc"),
                client.get_tokens(limit=3),
                client.get_network_exchange_rate(),
            ]
            
            transactions, tokens, exchange_rate = await asyncio.gather(*tasks)
            
            print(f"Found {len(transactions.transactions)} transactions")
            print(f"Found {len(tokens.tokens)} tokens")
            print(f"Exchange rate: {exchange_rate.current_rate.hbar_equivalent} HBAR = {exchange_rate.current_rate.cent_equivalent} cents")
            
        except Exception as e:
            print(f"Error: {e}")


def pagination_example():
    """Example of pagination."""
    print("\n=== Pagination Example ===")
    
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Manual pagination
        print("\n1. Manual pagination...")
        page_count = 0
        total_accounts = 0
        
        accounts = client.get_accounts(limit=10)
        while accounts and page_count < 3:  # Limit to 3 pages for demo
            page_count += 1
            total_accounts += len(accounts.accounts)
            print(f"Page {page_count}: {len(accounts.accounts)} accounts")
            
            if accounts.links.next:
                # Get next page - simplified for demo
                accounts = client.get_accounts(limit=10)
            else:
                break
        
        print(f"Total accounts processed: {total_accounts}")
        
        # Automatic pagination
        print("\n2. Automatic pagination...")
        page_count = 0
        total_accounts = 0
        
        for accounts_page in client.get_accounts_paginated(limit=10):
            page_count += 1
            total_accounts += len(accounts_page.accounts)
            print(f"Page {page_count}: {len(accounts_page.accounts)} accounts")
            
            # Stop after 3 pages for demo
            if page_count >= 3:
                break
        
        print(f"Total accounts processed: {total_accounts}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        client.close()


def contract_example():
    """Example of contract operations."""
    print("\n=== Contract Example ===")
    
    client = MirrorNodeClient.for_testnet()
    
    try:
        # Get contracts
        print("\n1. Getting contracts...")
        contracts = client.get_contracts(limit=5)
        print(f"Found {len(contracts.contracts)} contracts")
        
        for contract in contracts.contracts:
            print(f"  - {contract.contract_id}: {contract.evm_address}")
        
        # Contract call example (read-only)
        print("\n2. Contract call example...")
        try:
            # Example call to get contract name (if it has a name() function)
            result = client.call_contract({
                "to": "0x0000000000000000000000000000000000000001",  # Example address
                "data": "0x06fdde03",  # name() function signature
                "estimate": False
            })
            print(f"Contract call result: {result.result}")
        except Exception as e:
            print(f"Contract call failed (expected for demo): {e}")
        
        # Get contract results
        print("\n3. Getting contract results...")
        results = client.get_contract_results(limit=5)
        print(f"Found {len(results.results)} contract results")
        
        for result in results.results:
            print(f"  - {result.contract_id}: {result.result}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        client.close()


def main():
    """Main function to run all examples."""
    print("Hiero Mirror Node SDK Examples")
    print("=" * 50)
    
    # Run synchronous example
    sync_example()
    
    # Run asynchronous example
    asyncio.run(async_example())
    
    # Run pagination example
    pagination_example()
    
    # Run contract example
    contract_example()
    
    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    main()