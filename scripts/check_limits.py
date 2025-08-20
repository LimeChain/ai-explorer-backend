#!/usr/bin/env python3
"""
Script to check Redis rate limiting counters and cost tracking.
This script connects to Redis and shows current rate limiting and cost data.
"""
import os
import redis
import json
import time
import sys
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone

# Redis configuration (should match your app settings)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT_PREFIX = "rate_limit:ip:"
USER_COST_PREFIX = "cost_limit:user:"
GLOBAL_COST_KEY = "cost_limit:global"


def connect_to_redis() -> redis.Redis:
    """Connect to Redis with the same configuration as the app."""
    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            max_connections=20,
            retry_on_timeout=True,
            socket_timeout=5.0
        )
        # Test connection
        client.ping()
        print(f"✅ Connected to Redis at {REDIS_URL}")
        return client
    except redis.ConnectionError as e:
        print(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)


def get_all_rate_limit_keys(redis_client: redis.Redis) -> List[str]:
    """Get all rate limiting keys from Redis."""
    pattern = f"{RATE_LIMIT_PREFIX}*"
    keys = redis_client.keys(pattern)
    return [key.decode() if isinstance(key, bytes) else key for key in keys]


def get_all_user_cost_keys(redis_client: redis.Redis) -> List[str]:
    """Get all user cost tracking keys from Redis."""
    pattern = f"{USER_COST_PREFIX}*"
    keys = redis_client.keys(pattern)
    return [key.decode() if isinstance(key, bytes) else key for key in keys]


def get_global_cost_info(redis_client: redis.Redis) -> Dict[str, Any]:
    """Get global cost tracking information."""
    try:
        current_cost = redis_client.get(GLOBAL_COST_KEY)
        ttl = redis_client.ttl(GLOBAL_COST_KEY)
        
        return {
            "key": GLOBAL_COST_KEY,
            "current_cost": float(current_cost) if current_cost else 0.0,
            "ttl_seconds": ttl,
            "exists": current_cost is not None
        }
    except Exception as e:
        return {
            "key": GLOBAL_COST_KEY,
            "error": str(e)
        }


def get_user_cost_info(redis_client: redis.Redis, key: str) -> Dict[str, Any]:
    """Get detailed information about a user cost tracking key."""
    try:
        current_cost = redis_client.get(key)
        ttl = redis_client.ttl(key)
        
        return {
            "key": key,
            "user_hash": key.replace(USER_COST_PREFIX, ""),
            "current_cost": float(current_cost) if current_cost else 0.0,
            "ttl_seconds": ttl,
            "exists": current_cost is not None
        }
    except Exception as e:
        return {
            "key": key,
            "error": str(e)
        }


def get_key_info(redis_client: redis.Redis, key: str) -> Dict[str, Any]:
    """Get detailed information about a rate limiting key."""
    try:
        # Get all timestamps in the sorted set
        timestamps = redis_client.zrange(key, 0, -1, withscores=True)
        
        # Get TTL
        ttl = redis_client.ttl(key)
        
        # Convert timestamps to readable format
        requests = []
        current_time = time.time()
        
        for member, score in timestamps:
            timestamp = float(score)
            age_seconds = current_time - timestamp
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            
            requests.append({
                "timestamp": timestamp,
                "datetime": dt.isoformat(),
                "age_seconds": round(age_seconds, 2)
            })
        
        return {
            "key": key,
            "ip_hash": key.replace(RATE_LIMIT_PREFIX, ""),
            "request_count": len(requests),
            "ttl_seconds": ttl,
            "requests": requests
        }
        
    except Exception as e:
        return {
            "key": key,
            "error": str(e)
        }


def print_key_details(key_info: Dict[str, Any], show_requests: bool = False):
    """Print detailed information about a rate limiting key."""
    if "error" in key_info:
        print(f"❌ Error for key {key_info['key']}: {key_info['error']}")
        return
    
    ip_hash = key_info["ip_hash"][:16] + "..." if len(key_info["ip_hash"]) > 16 else key_info["ip_hash"]
    
    print(f"\n🔑 IP Hash: {ip_hash}")
    print(f"📊 Request count: {key_info['request_count']}")
    print(f"⏰ TTL: {key_info['ttl_seconds']} seconds")
    
    if show_requests and key_info["requests"]:
        print("📝 Recent requests:")
        for i, req in enumerate(key_info["requests"][-5:], 1):  # Show last 5 requests
            print(f"  {i}. {req['datetime']} ({req['age_seconds']}s ago)")


def print_user_cost_details(cost_info: Dict[str, Any]):
    """Print detailed information about a user cost tracking key."""
    if "error" in cost_info:
        print(f"❌ Error for key {cost_info['key']}: {cost_info['error']}")
        return
    
    user_hash = cost_info["user_hash"][:16] + "..." if len(cost_info["user_hash"]) > 16 else cost_info["user_hash"]
    
    print(f"\n🔑 User Hash: {user_hash}")
    print(f"💰 Current cost: ${cost_info['current_cost']:.6f}")
    print(f"⏰ TTL: {cost_info['ttl_seconds']} seconds")
    if not cost_info["exists"]:
        print("ℹ️  No cost data recorded for this user yet")


def print_global_cost_details(cost_info: Dict[str, Any]):
    """Print detailed information about global cost tracking."""
    if "error" in cost_info:
        print(f"❌ Error for key {cost_info['key']}: {cost_info['error']}")
        return
    
    print(f"\n🌍 Global Cost Tracking:")
    print(f"💰 Current cost: ${cost_info['current_cost']:.6f}")
    print(f"⏰ TTL: {cost_info['ttl_seconds']} seconds")
    if not cost_info["exists"]:
        print("ℹ️  No global cost data recorded yet")


def monitor_mode(redis_client: redis.Redis, refresh_seconds: int = 5):
    """Monitor rate limiting and cost tracking in real-time."""
    print(f"🔄 Monitoring mode - refreshing every {refresh_seconds}s (Ctrl+C to exit)")
    print("-" * 80)
    
    try:
        while True:
            # Clear screen (works on most terminals)
            print("\033[2J\033[H", end="")
            
            print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Redis Limits & Costs Monitor")
            print("-" * 80)
            
            # Rate limiting data
            rate_keys = get_all_rate_limit_keys(redis_client)
            cost_keys = get_all_user_cost_keys(redis_client)
            global_cost = get_global_cost_info(redis_client)
            
            # Rate limits section
            if not rate_keys:
                print("📭 No active rate limiting keys found")
            else:
                print(f"🔍 Found {len(rate_keys)} active rate limiting keys:")
                
                total_requests = 0
                for key in rate_keys:
                    key_info = get_key_info(redis_client, key)
                    if "error" not in key_info:
                        total_requests += key_info["request_count"]
                        print_key_details(key_info)
                
                print(f"\n📈 Total active requests across all keys: {total_requests}")
            
            # Cost tracking section
            print("\n" + "="*50 + " COST TRACKING " + "="*50)
            
            # Global cost
            print_global_cost_details(global_cost)
            
            # User costs
            if not cost_keys:
                print("\n📭 No active user cost tracking keys found")
            else:
                print(f"\n🔍 Found {len(cost_keys)} active user cost keys:")
                
                total_user_costs = 0
                for key in cost_keys:
                    cost_info = get_user_cost_info(redis_client, key)
                    if "error" not in cost_info:
                        total_user_costs += cost_info["current_cost"]
                        print_user_cost_details(cost_info)
                
                print(f"\n💰 Total user costs: ${total_user_costs:.6f}")
            
            print(f"\n⏳ Next refresh in {refresh_seconds}s...")
            time.sleep(refresh_seconds)
            
    except KeyboardInterrupt:
        print("\n⛔ Monitoring stopped by user")


def clear_all_rate_limits(redis_client: redis.Redis):
    """Clear all rate limiting data (useful for testing)."""
    keys = get_all_rate_limit_keys(redis_client)
    
    if not keys:
        print("📭 No rate limiting keys to clear")
        return
    
    print(f"🧹 Found {len(keys)} rate limiting keys to clear")
    
    # Ask for confirmation
    response = input("Are you sure you want to clear all rate limiting data? (y/N): ")
    if response.lower() != 'y':
        print("❌ Operation cancelled")
        return
    
    deleted_count = redis_client.delete(*keys)
    print(f"✅ Cleared {deleted_count} rate limiting keys")


def clear_all_costs(redis_client: redis.Redis):
    """Clear all cost tracking data (useful for testing)."""
    user_keys = get_all_user_cost_keys(redis_client)
    global_key_exists = redis_client.exists(GLOBAL_COST_KEY)
    
    total_keys = len(user_keys) + (1 if global_key_exists else 0)
    
    if total_keys == 0:
        print("📭 No cost tracking keys to clear")
        return
    
    print(f"🧹 Found {total_keys} cost tracking keys to clear:")
    print(f"  - {len(user_keys)} user cost keys")
    print(f"  - {'1 global cost key' if global_key_exists else '0 global cost keys'}")
    
    # Ask for confirmation
    response = input("Are you sure you want to clear all cost tracking data? (y/N): ")
    if response.lower() != 'y':
        print("❌ Operation cancelled")
        return
    
    deleted_count = 0
    
    # Clear user cost keys
    if user_keys:
        deleted_count += redis_client.delete(*user_keys)
    
    # Clear global cost key
    if global_key_exists:
        deleted_count += redis_client.delete(GLOBAL_COST_KEY)
    
    print(f"✅ Cleared {deleted_count} cost tracking keys")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    redis_client = connect_to_redis()
    
    if command == "list":
        rate_keys = get_all_rate_limit_keys(redis_client)
        cost_keys = get_all_user_cost_keys(redis_client)
        global_cost = get_global_cost_info(redis_client)
        
        show_details = "--details" in sys.argv
        show_requests = "--requests" in sys.argv
        show_costs = "--costs" in sys.argv or show_details
        
        # Rate limiting keys
        if not rate_keys:
            print("📭 No active rate limiting keys found")
        else:
            print(f"🔍 Found {len(rate_keys)} active rate limiting keys:")
            
            for key in rate_keys:
                key_info = get_key_info(redis_client, key)
                if show_details:
                    print_key_details(key_info, show_requests)
                else:
                    ip_hash = key_info.get("ip_hash", "unknown")[:16]
                    count = key_info.get("request_count", 0)
                    ttl = key_info.get("ttl_seconds", 0)
                    print(f"  🔑 {ip_hash}... ({count} requests, {ttl}s TTL)")
        
        # Cost tracking
        if show_costs:
            print("\n" + "="*30 + " COST TRACKING " + "="*30)
            
            # Global cost
            print_global_cost_details(global_cost)
            
            # User costs
            if not cost_keys:
                print("\n📭 No active user cost tracking keys found")
            else:
                print(f"\n🔍 Found {len(cost_keys)} active user cost keys:")
                
                for key in cost_keys:
                    cost_info = get_user_cost_info(redis_client, key)
                    if show_details:
                        print_user_cost_details(cost_info)
                    else:
                        user_hash = cost_info.get("user_hash", "unknown")[:16]
                        cost = cost_info.get("current_cost", 0)
                        ttl = cost_info.get("ttl_seconds", 0)
                        print(f"  🔑 {user_hash}... (${cost:.6f}, {ttl}s TTL)")
    
    elif command == "monitor":
        refresh_seconds = 5
        if len(sys.argv) > 2:
            try:
                refresh_seconds = int(sys.argv[2])
            except ValueError:
                print("❌ Invalid refresh interval, using 5 seconds")
        
        monitor_mode(redis_client, refresh_seconds)
    
    elif command == "clear":
        subcommand = sys.argv[2] if len(sys.argv) > 2 else "all"
        
        if subcommand == "rates" or subcommand == "all":
            clear_all_rate_limits(redis_client)
        
        if subcommand == "costs" or subcommand == "all":
            clear_all_costs(redis_client)
        
        if subcommand not in ["rates", "costs", "all"]:
            print(f"❌ Unknown clear subcommand: {subcommand}")
            print("Valid options: rates, costs, all")
    
    elif command == "costs":
        cost_keys = get_all_user_cost_keys(redis_client)
        global_cost = get_global_cost_info(redis_client)
        
        print("💰 Cost Tracking Details:")
        print("=" * 50)
        
        # Global cost
        print_global_cost_details(global_cost)
        
        # User costs
        if not cost_keys:
            print("\n📭 No active user cost tracking keys found")
        else:
            print(f"\n🔍 Found {len(cost_keys)} active user cost keys:")
            
            total_user_costs = 0
            for key in cost_keys:
                cost_info = get_user_cost_info(redis_client, key)
                if "error" not in cost_info:
                    total_user_costs += cost_info["current_cost"]
                    print_user_cost_details(cost_info)
            
            print(f"\n💰 Total user costs: ${total_user_costs:.6f}")
    
    elif command == "stats":
        rate_keys = get_all_rate_limit_keys(redis_client)
        cost_keys = get_all_user_cost_keys(redis_client)
        global_cost = get_global_cost_info(redis_client)
        
        print("📊 Rate Limiting & Cost Tracking Statistics:")
        print("=" * 50)
        
        # Rate limiting stats
        if not rate_keys:
            print("📭 No active rate limiting keys found")
        else:
            total_requests = 0
            active_rate_keys = 0
            
            for key in rate_keys:
                key_info = get_key_info(redis_client, key)
                if "error" not in key_info:
                    total_requests += key_info["request_count"]
                    active_rate_keys += 1
            
            print(f"🔑 Active IP addresses (rate limits): {active_rate_keys}")
            print(f"📈 Total requests: {total_requests}")
            if active_rate_keys > 0:
                avg_requests = total_requests / active_rate_keys
                print(f"📊 Average requests per IP: {avg_requests:.2f}")
        
        # Cost tracking stats
        print("\n💰 Cost Tracking:")
        print("-" * 30)
        
        # Global cost
        if global_cost.get("exists", False):
            print(f"🌍 Global cost: ${global_cost['current_cost']:.6f}")
        else:
            print("🌍 Global cost: No data")
        
        # User costs
        if not cost_keys:
            print("👥 User costs: No data")
        else:
            total_user_costs = 0
            active_cost_keys = 0
            
            for key in cost_keys:
                cost_info = get_user_cost_info(redis_client, key)
                if "error" not in cost_info and cost_info.get("exists", False):
                    total_user_costs += cost_info["current_cost"]
                    active_cost_keys += 1
            
            print(f"👥 Active users with costs: {active_cost_keys}")
            print(f"💰 Total user costs: ${total_user_costs:.6f}")
            if active_cost_keys > 0:
                avg_cost = total_user_costs / active_cost_keys
                print(f"📊 Average cost per user: ${avg_cost:.6f}")
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


def print_usage():
    """Print usage information."""
    print("🔍 Redis Rate Limit & Cost Tracking Checker")
    print()
    print("Usage:")
    print("  python scripts/check_limits.py list [--details] [--requests] [--costs]")
    print("    List all active rate limiting keys and optionally cost data")
    print("    --details: Show detailed information for each key")
    print("    --requests: Show individual request timestamps")
    print("    --costs: Show cost tracking data (implied by --details)")
    print()
    print("  python scripts/check_limits.py monitor [refresh_seconds]")
    print("    Monitor rate limiting and cost tracking in real-time (default: 5s refresh)")
    print()
    print("  python scripts/check_limits.py stats")
    print("    Show summary statistics for rate limits and costs")
    print()
    print("  python scripts/check_limits.py costs")
    print("    Show detailed cost tracking information only")
    print()
    print("  python scripts/check_limits.py clear [rates|costs|all]")
    print("    Clear data with confirmation (default: all)")
    print("    rates: Clear only rate limiting data")
    print("    costs: Clear only cost tracking data") 
    print("    all: Clear both rate limiting and cost data")
    print()
    print("Examples:")
    print("  python scripts/check_limits.py list")
    print("  python scripts/check_limits.py list --details --requests")
    print("  python scripts/check_limits.py list --costs")
    print("  python scripts/check_limits.py monitor 3")
    print("  python scripts/check_limits.py stats")
    print("  python scripts/check_limits.py costs")
    print("  python scripts/check_limits.py clear costs")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ Script interrupted by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")
