"""Rate limiting for API calls - per-endpoint support"""
import time
from collections import deque
from typing import Dict

class RateLimiter:
    """Thread-safe rate limiter with per-endpoint tracking"""
    
    def __init__(self, max_calls_per_minute: int = 100):
        self.max_calls = max_calls_per_minute
        self.calls = deque()
        # ✅ NEW: Per-endpoint tracking
        self.endpoint_calls: Dict[str, deque] = {}
    
    def wait_if_needed(self, endpoint_name: str = None):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # ✅ NEW: Use endpoint-specific limit if provided
        if endpoint_name:
            if endpoint_name not in self.endpoint_calls:
                self.endpoint_calls[endpoint_name] = deque()
            
            calls = self.endpoint_calls[endpoint_name]
            
            # Get endpoint-specific limit from config
            from core.config import get_config
            config = get_config()
            endpoint_config = config.get("endpoints", {}).get(endpoint_name, {})
            max_calls = endpoint_config.get("rate_limit_per_minute", 118)
        else:
            # Global limit
            calls = self.calls
            max_calls = self.max_calls
        
        # Remove calls older than 60 seconds
        while calls and calls[0] < now - 60:
            calls.popleft()
        
        # Check if we need to wait
        if len(calls) >= max_calls:
            sleep_time = calls[0] + 60 - now + 0.2
            if sleep_time > 0:
                print(f"⏳ Rate limit ({endpoint_name or 'global'}): sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        
        calls.append(now)
    
    def set_max_calls(self, max_calls: int):
        """Dynamically update max calls per minute (called by resource controller)"""
        old_max = self.max_calls
        self.max_calls = max_calls
        print(f"    🎛️  Rate limit adjusted: {old_max} → {max_calls} calls/min")