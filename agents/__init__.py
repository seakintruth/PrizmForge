import threading
from datetime import datetime

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
        self.worker_thread: threading.Thread | None = None
        self.task_id: str | None = None
        self.config = get_config()
        self.rc_config = self.config.get("resource_controller", {})
        self.token_budget = TokenBudget(get_db_path(), self.rc_config.get("max_tokens_per_day", 5_000_000))
        self.optimizer = HeuristicOptimizer()
        self.current_decision: ThrottleDecision | None = None
        self.decision_history: list[ThrottleDecision] = []
        self.throttling_disabled_until: datetime | None = None
