"""Multi-endpoint manager for different API providers"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging
from core.db_connection import get_db_connection

logger = logging.getLogger(__name__)

# Add this enum definition
class EndpointStatus(Enum):
    """Endpoint status values"""
    HEALTHY = "healthy"
    RATE_LIMITED = "rate_limited"
    TOKEN_EXHAUSTED = "token_exhausted"
    KEY_LOCKED = "key_locked"
    SERVER_ERROR = "server_error"
    UNAVAILABLE = "unavailable"

class EndpointConfig:
    """Configuration for a specific endpoint"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.base_url = config.get("base_url")
        self.api_key_name = config.get("api_key_name", "api_key")
        self.include_model_in_payload = config.get("include_model_in_payload", True)
        self.response_path = config.get("response_path", ["choices", 0, "message", "content"])
        self.key_management_url = config.get("key_management_url", "Contact your system administrator for access.")
        self.description = config.get("description", "")
        self.priority = config.get("priority", 50)
        self.rate_limit_per_minute = config.get("rate_limit_per_minute", 118)
        
        # Health tracking with persistence
        self.health = EndpointHealth(endpoint_name=name)
    
    def extract_response(self, data: Dict) -> str:
        """Extract response text using configured path"""
        result = data
        for key in self.response_path:
            if isinstance(key, int):
                result = result[key]
            else:
                result = result[key]
        return result
        
class EndpointHealth:
    """Track health status of an endpoint"""
    def __init__(self, endpoint_name: str = None):
        self.endpoint_name = endpoint_name
        self.status = EndpointStatus.HEALTHY
        self.last_error = None
        self.error_count = 0
        self.last_success = datetime.now()
        self.unavailable_until = None
        self.consecutive_failures = 0
        
        # Load from database if name provided
        if endpoint_name:
            self._load_from_db()
    
    def _load_from_db(self):
        """Load health status from database"""
        try:
            from core.db import get_db_path
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, error_count, consecutive_failures, 
                        last_success, unavailable_until
                    FROM endpoint_health
                    WHERE endpoint_name = ?
                """, (self.endpoint_name,))
                
                row = cursor.fetchone()
            
            if row:
                self.status = EndpointStatus(row[0])
                self.error_count = row[1]
                self.consecutive_failures = row[2]
                if row[3]:
                    self.last_success = datetime.fromisoformat(row[3])
                if row[4]:
                    self.unavailable_until = datetime.fromisoformat(row[4])
        except Exception as e:
            logger.warning(f"Failed to load endpoint health from DB: {e}")
    
    def _save_to_db(self):
        """Save health status to database"""
        if not self.endpoint_name:
            return
        
        try:
            from core.db import get_db_path

            with get_db_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO endpoint_health
                    (endpoint_name, status, error_count, consecutive_failures,
                    last_success, unavailable_until, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.endpoint_name,
                    self.status.value,
                    self.error_count,
                    self.consecutive_failures,
                    self.last_success.isoformat() if self.last_success else None,
                    self.unavailable_until.isoformat() if self.unavailable_until else None,
                    datetime.now().isoformat()
                ))
        except Exception as e:
            logger.warning(f"Failed to save endpoint health to DB: {e}")
    
    def is_available(self) -> bool:
        """Check if endpoint is currently available"""
        if self.unavailable_until is None:
            return True
        return datetime.now() >= self.unavailable_until
    
    def time_until_available(self) -> int:
        """Get seconds until endpoint is available"""
        if self.unavailable_until is None:
            return 0
        remaining = (self.unavailable_until - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def mark_success(self):
        """Mark successful call"""
        self.status = EndpointStatus.HEALTHY
        self.error_count = 0
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.unavailable_until = None
        self._save_to_db()
    
    def mark_failure(self, status: EndpointStatus, cooldown_minutes: int = None):
        """Mark failed call with configurable cooldown period"""
        self.status = status
        self.last_error = datetime.now()
        self.error_count += 1
        self.consecutive_failures += 1
        
        # Use provided cooldown or defaults
        if cooldown_minutes is None:
            if status == EndpointStatus.TOKEN_EXHAUSTED:
                cooldown_minutes = 15
            elif status == EndpointStatus.KEY_LOCKED:
                cooldown_minutes = 30
            elif status == EndpointStatus.RATE_LIMITED:
                cooldown_minutes = 2
            else:
                cooldown_minutes = 5
        
        self.unavailable_until = datetime.now() + timedelta(minutes=cooldown_minutes)
        self._save_to_db()

class EndpointManager:
    """Manage multiple API endpoints"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.endpoints = {}
        self.models = {}
        
        # Load endpoints
        for name, endpoint_config in config.get("endpoints", {}).items():
            self.endpoints[name] = EndpointConfig(name, endpoint_config)
            logger.info(f"Loaded endpoint: {name} - {endpoint_config.get('description')}")
        
        # Load models
        for model_name, model_config in config.get("models", {}).items():
            endpoint_name = model_config.get("endpoint")
            if endpoint_name not in self.endpoints:
                logger.warning(f"Model '{model_name}' references unknown endpoint '{endpoint_name}'")
                continue
            
            self.models[model_name] = {
                "endpoint": self.endpoints[endpoint_name],
                "config": model_config
            }
            logger.debug(f"Registered model: {model_name} -> {endpoint_name}")
        
        self.default_endpoint = self.endpoints.get(
            config.get("default_endpoint", "gemini")
        )
    
    def get_endpoint_for_model(self, model_name: Optional[str] = None) -> EndpointConfig:
        """Get endpoint configuration for a given model"""
        if not model_name:
            return self.default_endpoint
        
        model_info = self.models.get(model_name)
        if not model_info:
            logger.warning(f"Unknown model '{model_name}', using default endpoint")
            return self.default_endpoint
        
        return model_info["endpoint"]
    
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get configuration for a model"""
        model_info = self.models.get(model_name, {})
        return model_info.get("config", {})
    
    def get_api_key(self, endpoint: EndpointConfig) -> str:
        """Get API key for an endpoint"""
        # Try specific key name first
        api_key = self.config.get(endpoint.api_key_name)
        
        # Fall back to generic api_key
        if not api_key:
            api_key = self.config.get("api_key")
        
        if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE" or api_key == "YOUR_DATABRICKS_TOKEN_HERE":
            raise ValueError(f"API key not configured for endpoint: {endpoint.name}")
        
        return api_key
    
    def build_payload(self, 
                     endpoint: EndpointConfig,
                     model_name: Optional[str],
                     messages: List[Dict],
                     max_tokens: Optional[int] = None,
                     temperature: Optional[float] = None) -> Dict[str, Any]:
        """Build request payload for specific endpoint"""
        
        model_config = self.get_model_config(model_name) if model_name else {}
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens or model_config.get("max_output_tokens", 16384),
            "temperature": temperature if temperature is not None else model_config.get("temperature", 0.5)
        }
        
        # Add model field if endpoint requires it
        if endpoint.include_model_in_payload and model_name:
            payload["model"] = model_name
        
        return payload
    
    def validate_model(self, model_name: str) -> str:
        """Validate model exists and return it or default"""
        if not model_name:
            return None
        
        if model_name in self.models:
            return model_name
        
        # Model doesn't exist - get default from first available model
        available_models = list(self.models.keys())
        default_model = available_models[0] if available_models else None
        
        if default_model:
            logger.warning(f"Model '{model_name}' not found. Using '{default_model}'")
            logger.info(f"Available: {', '.join(available_models)}")
            return default_model
        
        return None
    
    def get_fallback_model(self, endpoint: EndpointConfig) -> Optional[Tuple[str, EndpointConfig]]:
        """Get fallback model and endpoint"""
        fallback_settings = self.config.get("fallback_settings", {})
        
        if not fallback_settings.get("enabled", True):
            return None
        
        # Get all available endpoints sorted by priority
        available = self.get_available_endpoints()
        
        # Filter out the current endpoint
        available = [ep for ep in available if ep.name != endpoint.name]
        
        if not available:
            return None
        
        # Get first model for the fallback endpoint
        fallback_endpoint = available[0]
        
        # Find a model that uses this endpoint
        for model_name, model_info in self.models.items():
            if model_info["endpoint"].name == fallback_endpoint.name:
                return (model_name, fallback_endpoint)
        
        return None
    
    def get_available_endpoints(self) -> List[EndpointConfig]:
        """Get list of currently available endpoints"""
        available = []
        for endpoint in self.endpoints.values():
            if endpoint.health.is_available():
                available.append(endpoint)
        
        # Sort by priority (lower number = higher priority)
        available.sort(key=lambda ep: ep.priority)
        return available
    
    def get_health_summary(self) -> Dict[str, Dict]:
        """Get health summary for all endpoints"""
        summary = {}
        for name, endpoint in self.endpoints.items():
            summary[name] = {
                "status": endpoint.health.status.value,
                "available": endpoint.health.is_available(),
                "error_count": endpoint.health.error_count,
                "consecutive_failures": endpoint.health.consecutive_failures,
                "last_success": endpoint.health.last_success.isoformat() if endpoint.health.last_success else None,
                "unavailable_until": endpoint.health.unavailable_until.isoformat() if endpoint.health.unavailable_until else None,
                "seconds_until_available": endpoint.health.time_until_available()
            }
        return summary

# Global singleton
_endpoint_manager = None

def get_endpoint_manager() -> EndpointManager:
    """Get global endpoint manager"""
    global _endpoint_manager
    if _endpoint_manager is None:
        from core.config import get_config
        config = get_config()
        _endpoint_manager = EndpointManager(config)
    return _endpoint_manager