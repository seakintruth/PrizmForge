import threading
from datetime import datetime
from typing import List, Optional

from agents.resource_controller_worker import (
    HeuristicOptimizer,
    ThrottleDecision,
)
from core.config import get_config
from core.db import get_db_path
from core.token_budget import TokenBudget


class ResourceController:
    """Resource controller with throttling capabilities"""

    def __init__(self):
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.task_id: Optional[str] = None
        self.config = get_config()
        self.rc_config = self.config.get("resource_controller", {})
        self.token_budget = TokenBudget(get_db_path(), self.rc_config.get("max_tokens_per_day", 5_000_000))
        self.optimizer = HeuristicOptimizer()
        self.current_decision: Optional[ThrottleDecision] = None
        self.decision_history: List[ThrottleDecision] = []
        self.throttling_disabled_until: Optional[datetime] = None
