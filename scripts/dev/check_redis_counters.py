#!/usr/bin/env python3
"""
Script to check Redis rate limiting counters.
This script connects to Redis and shows current rate limiting data.
"""
import os
import redis
import json
import time
import sys
from typing import Dict, List, Any
from datetime import datetime, timezone

# Redis configuration (should match your app settings)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT_PREFIX = "rate_limit:ip:"


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


def monitor_mode(redis_client: redis.Redis, refresh_seconds: int = 5):
    """Monitor rate limiting in real-time."""
    print(f"🔄 Monitoring mode - refreshing every {refresh_seconds}s (Ctrl+C to exit)")
    print("-" * 80)
    
    try:
        while True:
            # Clear screen (works on most terminals)
            print("\033[2J\033[H", end="")
            
            print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Redis Rate Limit Monitor")
            print("-" * 80)
            
            keys = get_all_rate_limit_keys(redis_client)
            
            if not keys:
                print("📭 No active rate limiting keys found")
            else:
                print(f"🔍 Found {len(keys)} active rate limiting keys:")
                
                total_requests = 0
                for key in keys:
                    key_info = get_key_info(redis_client, key)
                    if "error" not in key_info:
                        total_requests += key_info["request_count"]
                        print_key_details(key_info)
                
                print(f"\n📈 Total active requests across all keys: {total_requests}")
            
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


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    redis_client = connect_to_redis()
    
    if command == "list":
        keys = get_all_rate_limit_keys(redis_client)
        
        if not keys:
            print("📭 No active rate limiting keys found")
            return
        
        print(f"🔍 Found {len(keys)} active rate limiting keys:")
        
        show_details = "--details" in sys.argv
        show_requests = "--requests" in sys.argv
        
        for key in keys:
            key_info = get_key_info(redis_client, key)
            if show_details:
                print_key_details(key_info, show_requests)
            else:
                ip_hash = key_info.get("ip_hash", "unknown")[:16]
                count = key_info.get("request_count", 0)
                ttl = key_info.get("ttl_seconds", 0)
                print(f"  🔑 {ip_hash}... ({count} requests, {ttl}s TTL)")
    
    elif command == "monitor":
        refresh_seconds = 5
        if len(sys.argv) > 2:
            try:
                refresh_seconds = int(sys.argv[2])
            except ValueError:
                print("❌ Invalid refresh interval, using 5 seconds")
        
        monitor_mode(redis_client, refresh_seconds)
    
    elif command == "clear":
        clear_all_rate_limits(redis_client)
    
    elif command == "stats":
        keys = get_all_rate_limit_keys(redis_client)
        
        if not keys:
            print("📭 No active rate limiting keys found")
            return
        
        total_requests = 0
        active_keys = 0
        
        print("📊 Rate Limiting Statistics:")
        print("-" * 40)
        
        for key in keys:
            key_info = get_key_info(redis_client, key)
            if "error" not in key_info:
                total_requests += key_info["request_count"]
                active_keys += 1
        
        print(f"🔑 Active IP addresses: {active_keys}")
        print(f"📈 Total requests: {total_requests}")
        if active_keys > 0:
            avg_requests = total_requests / active_keys
            print(f"📊 Average requests per IP: {avg_requests:.2f}")
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


def print_usage():
    """Print usage information."""
    print("🔍 Redis Rate Limit Counter Checker")
    print()
    print("Usage:")
    print("  python scripts/check_redis_counters.py list [--details] [--requests]")
    print("    List all active rate limiting keys")
    print("    --details: Show detailed information for each key")
    print("    --requests: Show individual request timestamps")
    print()
    print("  python scripts/check_redis_counters.py monitor [refresh_seconds]")
    print("    Monitor rate limiting in real-time (default: 5s refresh)")
    print()
    print("  python scripts/check_redis_counters.py stats")
    print("    Show summary statistics")
    print()
    print("  python scripts/check_redis_counters.py clear")
    print("    Clear all rate limiting data (with confirmation)")
    print()
    print("Examples:")
    print("  python scripts/check_redis_counters.py list")
    print("  python scripts/check_redis_counters.py list --details --requests")
    print("  python scripts/check_redis_counters.py monitor 3")
    print("  python scripts/check_redis_counters.py stats")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ Script interrupted by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")
