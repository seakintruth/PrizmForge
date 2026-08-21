"""
./agents/resource_controller_worker.py
Resource Controller - Heuristic Implementation
NO EXTERNAL DEPENDENCIES - Pure Python stdlib

This controller ACTUALLY enforces throttling by:
1. Adjusting background agent feeder intervals
2. Enabling/disabling specific agents based on value
3. Overriding rate limits dynamically
4. Downgrading models to faster/cheaper ones
5. Learning from agent performance over time

Philosophy:
- Smart context manager handles file limits (no artificial restrictions)
- Resource controller focuses on rate limiting and agent scheduling
- Adaptive learning: agents that generate good feedback get more budget
- Respects human priorities from config
"""

import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from agents.base import get_rate_limiter
from agents.parallel_workers import get_agent_pool
from core.config import get_config
from core.db import get_db_path
from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.token_budget import TokenBudget


@dataclass
class AgentProfile:
    """Resource and value profile for an agent"""

    name: str
    avg_tokens_per_call: float
    avg_duration_seconds: float
    feedback_value_score: float  # 0.0 - 1.0, learned over time
    total_calls: int = 0
    total_feedback_generated: int = 0
    last_updated: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentProfile":
        return cls(**data)


@dataclass
class ResourceState:
    """Current system resource state snapshot"""

    tokens_used_in_window: int
    tokens_remaining: int
    max_tokens: int
    current_burn_rate: float  # tokens/minute
    api_calls_last_minute: int
    api_rate_limit: int
    budget_percentage: float
    time_remaining_in_window: float  # minutes

    def __str__(self):
        return (
            f"Budget: {self.budget_percentage:.1%} "
            f"({self.tokens_remaining:,}/{self.max_tokens:,} tokens), "
            f"Burn: {self.current_burn_rate:.0f} tok/min, "
            f"API: {self.api_calls_last_minute}/{self.api_rate_limit} calls/min"
        )


@dataclass
class ThrottleDecision:
    """Concrete throttling decision to be enforced"""

    level: str  # CRITICAL, AGGRESSIVE, MODERATE, NORMAL
    background_feeder_interval: int  # seconds between random file feeds
    active_agents: list[str]  # Which background agents to run
    rate_limit_per_minute: int  # Override global rate limit
    model_downgrades: dict[str, str]  # agent_name -> "endpoint/model_name"
    reasoning: str  # Human-readable explanation

    def to_dict(self) -> dict:
        return asdict(self)


class HeuristicOptimizer:
    """
    Rule-based resource optimizer with adaptive learning

    Strategy:
    - Tracks agent performance (tokens used, feedback value generated)
    - Learns which agents provide most value per token
    - Respects human-defined priorities from config
    - Makes budget-aware throttling decisions
    - Adapts over time based on actual performance
    """

    def __init__(self):
        self.config = get_config()
        self.rc_config = self.config.get("resource_controller", {})

        # Load or initialize agent profiles
        self.agent_profiles = self._load_agent_profiles()

        # Human priority categories from config
        self.priority_categories = self._get_priority_categories()

        # Throttling thresholds (budget percentage)
        self.thresholds = {
            "critical": 0.05,  # < 5% budget
            "aggressive": 0.20,  # < 20% budget
            "moderate": 0.50,  # < 50% budget
            "normal": 1.0,  # >= 50% budget
        }

    def _model_downgrades_for(self, tier: str) -> dict[str, str]:
        """
        Load agent -> model downgrade map for a throttle tier.
        Values are now in "endpoint/model" format (e.g. "gemini/gemini-3.7-flash").
        """
        md = self.rc_config.get("model_downgrades") or {}
        tier_map = md.get(tier)

        if not isinstance(tier_map, dict):
            return {}

        downgrades = {}
        for agent, model_ref in tier_map.items():
            if str(agent).startswith("_"):
                continue
            if isinstance(model_ref, str) and model_ref.strip():
                downgrades[str(agent)] = model_ref.strip()

        return downgrades

    def _get_priority_categories(self) -> list[str]:
        """Get human-defined priority categories from config"""
        goals = self.rc_config.get("project_goals", {})
        return goals.get("priority_focus", ["security", "performance"])

    def _load_agent_profiles(self) -> dict[str, AgentProfile]:
        """Load agent profiles from database or initialize defaults"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Load existing profiles
                cursor.execute("SELECT agent_name, profile_json FROM agent_profiles")
                rows = cursor.fetchall()

            profiles = {}
            for agent_name, profile_json in rows:
                try:
                    data = json.loads(profile_json)
                    profiles[agent_name] = AgentProfile.from_dict(data)
                except Exception as e:
                    print(f"    ⚠️  Exception handled in resource_controller_worker.py: {e}")

            # Fill in defaults for missing agents
            defaults = self._get_default_profiles()
            for name, profile in defaults.items():
                if name not in profiles:
                    profiles[name] = profile

            return profiles

        except Exception as e:
            print(f"    ⚠️  Failed to load agent profiles: {e}")
            return self._get_default_profiles()

    def _get_default_profiles(self) -> dict[str, AgentProfile]:
        """Default agent resource profiles (initial estimates)"""
        return {
            "jr_reviewer": AgentProfile(
                name="jr_reviewer",
                avg_tokens_per_call=2000.0,
                avg_duration_seconds=3.0,
                feedback_value_score=0.8,  # High value - finds bugs
            ),
            "jr_researcher": AgentProfile(
                name="jr_researcher",
                avg_tokens_per_call=2500.0,
                avg_duration_seconds=4.0,
                feedback_value_score=0.6,  # Medium value - suggests improvements
            ),
            "tech_writer": AgentProfile(
                name="tech_writer",
                avg_tokens_per_call=1500.0,
                avg_duration_seconds=2.5,
                feedback_value_score=0.4,  # Lower value - docs improvements
            ),
            "prioritizer": AgentProfile(
                name="prioritizer",
                avg_tokens_per_call=1000.0,
                avg_duration_seconds=2.0,
                feedback_value_score=1.0,  # Critical - always run
            ),
            "archivist": AgentProfile(
                name="archivist",
                avg_tokens_per_call=1200.0,
                avg_duration_seconds=3.0,
                feedback_value_score=0.3,  # Can defer if needed
            ),
            "project_reporter": AgentProfile(
                name="project_reporter",
                avg_tokens_per_call=2000.0,
                avg_duration_seconds=5.0,
                feedback_value_score=0.2,  # Lowest priority - reporting only
            ),
        }

    def _save_agent_profiles(self):
        """Persist agent profiles to database"""
        try:
            with get_db_connection() as conn:
                for name, profile in self.agent_profiles.items():
                    profile.last_updated = datetime.now().isoformat()
                    profile_json = json.dumps(profile.to_dict())

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO agent_profiles
                        (agent_name, profile_json, last_updated)
                        VALUES (?, ?, ?)
                    """,
                        (name, profile_json, profile.last_updated),
                    )

        except Exception as e:
            print(f"    ⚠️  Failed to save agent profiles: {e}")

    def optimize(self, state: ResourceState) -> ThrottleDecision:
        """
        Make throttling decision based on current state

        Strategy:
        1. Determine throttle level based on budget percentage
        2. Select agents to keep active based on value scores
        3. Adjust intervals and limits proportionally
        4. Apply model downgrades if needed
        """

        # Check feedback backlog FIRST
        backlog_decision = self._check_feedback_backlog(state)
        if backlog_decision:
            return backlog_decision

        budget_pct = state.budget_percentage

        # Determine throttle level
        if budget_pct < self.thresholds["critical"]:
            return self._throttle_critical(state)
        elif budget_pct < self.thresholds["aggressive"]:
            return self._throttle_aggressive(state)
        elif budget_pct < self.thresholds["moderate"]:
            return self._throttle_moderate(state)
        else:
            return self._throttle_normal(state)

    def _check_feedback_backlog(self, state: ResourceState) -> ThrottleDecision | None:
        """
        Check if feedback backlog is too high

        Strategy:
        - If 300+ unaddressed feedback items → STOP background agents
        - Only run: prioritizer (organize), developer (fix)
        """
        try:
            from core.db_connection import get_db_connection

            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT COUNT(*) FROM agent_feedback
                    WHERE addressed = 0
                """)

                unaddressed_count = cursor.fetchone()[0]

            # Threshold: 300+ unaddressed items = STOP generating more
            if unaddressed_count >= 300:
                return ThrottleDecision(
                    level="BACKLOG_PROCESSING",
                    background_feeder_interval=9999,  # Effectively disable
                    active_agents=["prioritizer"],  # Only prioritizer
                    rate_limit_per_minute=max(30, int(state.api_rate_limit * 0.5)),
                    model_downgrades=self._model_downgrades_for("backlog_processing"),
                    reasoning=(
                        f"🚨 FEEDBACK BACKLOG: {unaddressed_count} unaddressed items. "
                        f"Pausing background agents (jr_reviewer, etc.). "
                        f"Allowing ONLY prioritizer to organize existing feedback. "
                        f"Developer will work through backlog in priority order."
                    ),
                )

            # Warning threshold: 150-299 items = Slow down
            elif unaddressed_count >= 150:
                return ThrottleDecision(
                    level="BACKLOG_WARNING",
                    background_feeder_interval=300,  # 5 min (very slow)
                    active_agents=[
                        "jr_reviewer",
                        "prioritizer",
                    ],  # Only 1 + prioritizer
                    rate_limit_per_minute=max(40, int(state.api_rate_limit * 0.6)),
                    model_downgrades={},
                    reasoning=(
                        f"⚠️  FEEDBACK BACKLOG: {unaddressed_count} unaddressed items. "
                        f"Reducing background agent activity to prevent overload. "
                        f"Only jr_reviewer active. Prioritizer organizing feedback."
                    ),
                )

            return None  # No backlog throttling needed

        except Exception as e:
            print(f"    ⚠️  Failed to check feedback backlog: {e}")
            return None

    def _throttle_critical(self, state: ResourceState) -> ThrottleDecision:
        """
        CRITICAL mode: < 5% budget remaining
        Emergency conservation - only prioritizer runs
        """
        return ThrottleDecision(
            level="CRITICAL",
            background_feeder_interval=300,  # 5 minutes
            active_agents=["prioritizer"],  # Only prioritizer
            rate_limit_per_minute=max(10, int(state.api_rate_limit * 0.1)),
            model_downgrades=self._model_downgrades_for("critical"),
            reasoning=(
                f"🚨 CRITICAL: {state.budget_percentage:.1%} budget remaining. "
                f"Emergency conservation mode. Only prioritizer active. "
                f"Model downgrades from config applied. "
                f"Rate limit: {max(10, int(state.api_rate_limit * 0.1))} calls/min."
            ),
        )

    def _throttle_aggressive(self, state: ResourceState) -> ThrottleDecision:
        """
        AGGRESSIVE mode: 5-20% budget remaining
        Keep prioritizer + highest value agent only
        """
        # Rank agents by value (excluding prioritizer)
        ranked_agents = self._rank_agents_by_value(exclude=["prioritizer"])

        # Keep top 1 background agent + prioritizer
        active_background = [ranked_agents[0]] if ranked_agents else []
        active_agents = ["prioritizer", *active_background]

        return ThrottleDecision(
            level="AGGRESSIVE",
            background_feeder_interval=180,  # 3 minutes
            active_agents=active_agents,
            rate_limit_per_minute=max(20, int(state.api_rate_limit * 0.3)),
            model_downgrades=self._model_downgrades_for("aggressive"),
            reasoning=(
                f"⚠️  AGGRESSIVE: {state.budget_percentage:.1%} budget remaining. "
                f"Conserving resources aggressively. "
                f"Active agents: {', '.join(active_agents)}. "
                f"Background agents use configured downgrade models. "
                f"Rate limit: {max(20, int(state.api_rate_limit * 0.3))} calls/min."
            ),
        )

    def _throttle_moderate(self, state: ResourceState) -> ThrottleDecision:
        """
        MODERATE mode: 20-50% budget remaining
        Keep prioritizer + top 2 highest value agents
        """
        # Rank agents by value
        ranked_agents = self._rank_agents_by_value(exclude=["prioritizer"])

        # Keep top 2 background agents + prioritizer
        active_background = ranked_agents[:2] if len(ranked_agents) >= 2 else ranked_agents
        active_agents = ["prioritizer", *active_background]

        # Add archivist if budget allows
        if state.budget_percentage > 0.3 and "archivist" not in active_agents:
            active_agents.append("archivist")

        return ThrottleDecision(
            level="MODERATE",
            background_feeder_interval=90,  # 1.5 minutes
            active_agents=active_agents,
            rate_limit_per_minute=max(40, int(state.api_rate_limit * 0.6)),
            model_downgrades=self._model_downgrades_for("moderate"),
            reasoning=(
                f"⚡ MODERATE: {state.budget_percentage:.1%} budget remaining. "
                f"Reducing activity to conserve budget. "
                f"Active agents: {', '.join(active_agents)}. "
                f"Some agents using configured downgrade models. "
                f"Rate limit: {max(40, int(state.api_rate_limit * 0.6))} calls/min."
            ),
        )

    def _throttle_normal(self, state: ResourceState) -> ThrottleDecision:
        """
        NORMAL mode: > 50% budget remaining
        All agents active at full capacity
        """
        return ThrottleDecision(
            level="NORMAL",
            background_feeder_interval=30,  # 30 seconds
            active_agents=[
                "jr_reviewer",
                "jr_researcher",
                "tech_writer",
                "prioritizer",
                "archivist",
                "project_reporter",
            ],
            rate_limit_per_minute=state.api_rate_limit,
            model_downgrades={},  # No downgrades
            reasoning=(
                f"✅ NORMAL: {state.budget_percentage:.1%} budget remaining. "
                f"Healthy budget. All agents active at full capacity. "
                f"No throttling applied. "
                f"Rate limit: {state.api_rate_limit} calls/min."
            ),
        )

    def _rank_agents_by_value(self, exclude: list[str] | None = None) -> list[str]:
        """
        Rank agents by current value score

        Value = base_score * priority_alignment * efficiency

        This adapts over time as we learn which agents provide most value
        """
        exclude = exclude or []

        scores = {}
        for name, profile in self.agent_profiles.items():
            if name in exclude:
                continue

            # Base value (learned from feedback generation)
            base_value = profile.feedback_value_score

            # Boost if agent aligns with human priorities
            priority_boost = self._get_priority_boost(name)

            # Efficiency: feedback per call
            if profile.total_calls > 0:
                efficiency = profile.total_feedback_generated / profile.total_calls
                performance_factor = min(1.5, 1.0 + efficiency * 0.5)
            else:
                performance_factor = 1.0

            # Final score
            scores[name] = base_value * priority_boost * performance_factor

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [name for name, score in ranked]

    def _get_priority_boost(self, agent_name: str) -> float:
        """
        Get priority boost for agent based on human-defined priorities

        Example: If priorities are ["security", "performance"]
        and jr_reviewer finds security issues, it gets boosted
        """
        # Heuristic mapping of agents to categories
        agent_strengths = {
            "jr_reviewer": ["security", "bug", "correctness"],
            "jr_researcher": ["performance", "optimization", "architecture"],
            "tech_writer": ["documentation", "maintainability", "readability"],
        }

        if agent_name not in agent_strengths:
            return 1.0

        strengths = agent_strengths[agent_name]

        # Check overlap with human priorities
        overlap = len(set(strengths) & set(self.priority_categories))

        if overlap > 0:
            return 1.0 + (overlap * 0.3)  # 30% boost per matching priority

        return 1.0

    def update_agent_performance(
        self,
        agent_name: str,
        tokens_used: int,
        duration: float,
        feedback_generated: int,
    ):
        """
        Learn from agent performance over time

        Uses exponential moving average for smoothing
        Adjusts value score based on feedback generation
        """
        if agent_name not in self.agent_profiles:
            return

        profile = self.agent_profiles[agent_name]

        # Update counters
        profile.total_calls += 1
        profile.total_feedback_generated += feedback_generated

        # Exponential moving average (10% new, 90% old)
        alpha = 0.1

        profile.avg_tokens_per_call = alpha * tokens_used + (1 - alpha) * profile.avg_tokens_per_call

        profile.avg_duration_seconds = alpha * duration + (1 - alpha) * profile.avg_duration_seconds

        # Adjust value score based on feedback generation
        if feedback_generated > 0:
            # Agent generated useful feedback - increase value slightly
            profile.feedback_value_score = min(
                1.0,
                profile.feedback_value_score * 1.02,  # 2% increase
            )
        elif profile.total_calls > 10:  # Only penalize after warmup
            # No feedback after warmup - decrease value slightly
            profile.feedback_value_score = max(
                0.1,
                profile.feedback_value_score * 0.99,  # 1% decrease
            )

        # Save periodically (every 10 calls)
        if profile.total_calls % 10 == 0:
            self._save_agent_profiles()


class ResourceControllerWorker:
    """
    Resource controller that ACTUALLY enforces throttling

    NO EXTERNAL DEPENDENCIES - Pure Python implementation

    Responsibilities:
    - Monitor token budget and API rate usage
    - Decide throttling level based on heuristics
    - Directly control: agent pool, rate limiter, model selection
    - Learn from agent performance over time
    - Respect human-defined priorities
    """

    def __init__(self):
        self.running = False
        self.worker_thread: threading.Thread | None = None
        self.task_id: str | None = None
        self.config = get_config()
        self.rc_config = self.config.get("resource_controller", {})
        self.token_budget = TokenBudget(get_db_path(), self.rc_config.get("max_tokens_per_day", 50_000_000))
        self.optimizer = HeuristicOptimizer()
        self.current_decision: ThrottleDecision | None = None
        self.decision_history: list[ThrottleDecision] = []
        self.throttling_disabled_until: datetime | None = None

    def start(self, task_id: str):
        """Start resource controller worker"""
        if self.running:
            return

        self.running = True
        self.task_id = task_id

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="resource-controller-worker")
        self.worker_thread.start()
        print("    ⚖️  Started Resource Controller (heuristic, adaptive)")

    def stop(self):
        """Stop resource controller worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)

        # Save final agent profiles (learned performance data)
        self.optimizer._save_agent_profiles()

        print("    🛑 Stopped Resource Controller")

    def _worker_loop(self):
        """Main control loop - monitors and adjusts resources"""
        check_interval = self.rc_config.get("check_interval_seconds", 30)

        while self.running:
            try:
                time.sleep(check_interval)
                if not self.running:
                    break

                # Skip normal throttling if temporarily disabled
                if self._is_throttling_disabled():
                    print("    🔓 Throttling temporarily disabled — skipping optimization cycle")
                    continue

                # Gather current state
                state = self._gather_resource_state()

                # Optimize (heuristic decision making)
                decision = self.optimizer.optimize(state)

                # Apply if changed significantly
                if self._should_apply_decision(decision):
                    self._apply_decision(decision, state)
                    self.current_decision = decision
                    self.decision_history.append(decision)

                    if len(self.decision_history) > 100:
                        self.decision_history = self.decision_history[-100:]

            except Exception as e:
                print(f"    ⚠️  Resource Controller error: {e}")
                import traceback

                traceback.print_exc()
                time.sleep(60)

    def _gather_resource_state(self) -> ResourceState:
        """Gather current system resource state snapshot"""

        # Token usage
        self.token_budget.load_from_db()
        tokens_used = self.token_budget.get_used()
        max_tokens = self.rc_config.get("max_tokens_per_day", 50_000_000)
        tokens_remaining = max(0, max_tokens - tokens_used)
        budget_pct = tokens_remaining / max(max_tokens, 1)

        # Burn rate (tokens per minute in last 10 minutes)
        burn_rate = self._compute_burn_rate()

        # API rate limit
        rate_config = self.config.get("rate_limit", {})
        api_rate_limit = rate_config.get("max_calls_per_minute", 118)

        # Recent API calls
        api_calls_last_minute = self._count_recent_api_calls()

        # Time remaining in window (24h rolling window)
        time_remaining = 24 * 60  # minutes

        return ResourceState(
            tokens_used_in_window=tokens_used,
            tokens_remaining=tokens_remaining,
            max_tokens=max_tokens,
            current_burn_rate=burn_rate,
            api_calls_last_minute=api_calls_last_minute,
            api_rate_limit=api_rate_limit,
            budget_percentage=budget_pct,
            time_remaining_in_window=time_remaining,
        )

    def _compute_burn_rate(self) -> float:
        """Compute tokens per minute over last 10 minutes"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                ten_min_ago = (datetime.now() - timedelta(minutes=10)).isoformat()

                cursor.execute(
                    """
                    SELECT SUM(tokens_used)
                    FROM token_log
                    WHERE timestamp > ?
                """,
                    (ten_min_ago,),
                )

                result = cursor.fetchone()

            if result and result[0]:
                # Tokens used in last 10 min / 10 = tokens per minute
                return result[0] / 10.0
            return 0.0

        except Exception:
            return 0.0

    def _count_recent_api_calls(self) -> int:
        """Count API calls in last minute (approximate from token log)"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                one_min_ago = (datetime.now() - timedelta(minutes=1)).isoformat()

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM token_log
                    WHERE timestamp > ?
                """,
                    (one_min_ago,),
                )

                result = cursor.fetchone()

            return result[0] if result else 0

        except Exception:
            return 0

    def _should_apply_decision(self, new_decision: ThrottleDecision) -> bool:
        """Check if decision changed enough to warrant reapplication"""
        if self.current_decision is None:
            return True

        curr = self.current_decision

        # Check significant changes
        level_changed = new_decision.level != curr.level

        interval_changed = abs(new_decision.background_feeder_interval - curr.background_feeder_interval) > 15  # > 15 seconds difference

        agents_changed = set(new_decision.active_agents) != set(curr.active_agents)

        rate_changed = abs(new_decision.rate_limit_per_minute - curr.rate_limit_per_minute) > 10  # > 10 calls/min difference

        return level_changed or interval_changed or agents_changed or rate_changed

    def _apply_decision(self, decision: ThrottleDecision, state: ResourceState):
        """
        ACTUALLY APPLY throttling decisions to system components

        This is the enforcement layer - changes are applied immediately:
        1. Background agent pool (feeder interval, active agents)
        2. Rate limiter (max calls per minute)
        3. Model overrides (stored for agents to check)
        4. Orchestrator notification (for critical situations)
        """
        print(f"\n    ⚖️  Resource Decision [{decision.level}]:")
        print(f"       State: {state}")
        print(f"       Active: {', '.join(decision.active_agents)}")
        print(f"       Feeder: {decision.background_feeder_interval}s")
        print(f"       Rate: {decision.rate_limit_per_minute} calls/min")
        if decision.model_downgrades:
            print(f"       Downgrades: {len(decision.model_downgrades)} agents")
        print()

        # 1. Adjust background agent pool
        try:
            agent_pool = get_agent_pool()

            if hasattr(agent_pool, "set_feeder_interval"):
                agent_pool.set_feeder_interval(decision.background_feeder_interval)

            if hasattr(agent_pool, "set_active_agents"):
                agent_pool.set_active_agents(decision.active_agents)
        except Exception as e:
            print(f"    ⚠️  Failed to adjust agent pool: {e}")

        # 2. Adjust rate limiter
        try:
            rate_limiter = get_rate_limiter(None)
            if hasattr(rate_limiter, "set_max_calls"):
                rate_limiter.set_max_calls(decision.rate_limit_per_minute)
        except Exception as e:
            print(f"    ⚠️  Failed to adjust rate limiter: {e}")

        # 3. Store model overrides for agents to check
        self._store_model_overrides(decision.model_downgrades)

        # 4. Notify orchestrator (only on significant changes)
        if decision.level in ["CRITICAL", "AGGRESSIVE"]:
            self._notify_orchestrator(decision, state)

        # 5. Log decision to database for analysis
        self._log_decision(decision, state)

    def _store_model_overrides(self, downgrades: dict[str, str]):
        """Store model override preferences for agents"""
        if not downgrades:
            return

        try:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM resource_model_overrides")

                for agent, model_ref in downgrades.items():
                    if model_ref:  # only store non-empty
                        conn.execute(
                            """
                            INSERT INTO resource_model_overrides
                            (agent_name, override_model, applied_at)
                            VALUES (?, ?, ?)
                            """,
                            (agent, model_ref, datetime.now().isoformat()),
                        )
        except Exception as e:
            print(f"    ⚠️  Failed to store model overrides: {e}")

    def _notify_orchestrator(self, decision: ThrottleDecision, state: ResourceState):
        """Notify orchestrator of critical resource constraints"""

        priority_map = {
            "CRITICAL": "CRITICAL",
            "AGGRESSIVE": "HIGH",
            "MODERATE": "MEDIUM",
            "NORMAL": "LOW",
        }

        emoji_map = {
            "CRITICAL": "🚨",
            "AGGRESSIVE": "⚠️",
            "MODERATE": "⚡",
            "NORMAL": "✅",
        }

        emoji = emoji_map.get(decision.level, "ℹ️")

        message = f"""{emoji} Resource Controller [{decision.level}]

{decision.reasoning}

Current State:
• Budget: {state.budget_percentage:.1%} remaining ({state.tokens_remaining:,} tokens)
• Burn rate: {state.current_burn_rate:.0f} tokens/minute
• API calls: {state.api_calls_last_minute}/{state.api_rate_limit} per minute

Actions Taken:
• Active agents: {", ".join(decision.active_agents)}
• Feeder interval: {decision.background_feeder_interval}s
• Rate limit: {decision.rate_limit_per_minute} calls/min
• Model downgrades: {len(decision.model_downgrades)} agent(s)

Recommendation: {self._get_recommendation(decision)}"""

        post_message(
            "resource_controller",
            "orchestrator",
            message,
            self.task_id or "global",
            priority_map.get(decision.level, "MEDIUM"),
        )

    def _get_recommendation(self, decision: ThrottleDecision) -> str:
        """Get actionable recommendation for orchestrator"""
        if decision.level == "CRITICAL":
            return "Focus ONLY on highest-priority human requests. Defer all other work."
        elif decision.level == "AGGRESSIVE":
            return "Prioritize critical and high-priority items only. Defer optimization work."
        elif decision.level == "MODERATE":
            return "Continue current work but avoid starting new large tasks."
        else:
            return "Normal operation. All systems available."

    def _log_decision(self, decision: ThrottleDecision, state: ResourceState):
        """Log decision to database for analysis"""
        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO resource_decisions
                    (timestamp, task_id, level, budget_percentage, tokens_remaining,
                    burn_rate, feeder_interval, active_agents, rate_limit, reasoning)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        datetime.now().isoformat(),
                        self.task_id,
                        decision.level,
                        state.budget_percentage,
                        state.tokens_remaining,
                        state.current_burn_rate,
                        decision.background_feeder_interval,
                        ",".join(decision.active_agents),
                        decision.rate_limit_per_minute,
                        decision.reasoning,
                    ),
                )

        except Exception as e:
            print(f"    ⚠️  Failed to log decision: {e}")

    def get_current_decision(self) -> ThrottleDecision | None:
        """Get current throttle decision (for status commands)"""
        return self.current_decision

    def get_decision_history(self, limit: int = 10) -> list[ThrottleDecision]:
        """Get recent decision history"""
        return self.decision_history[-limit:] if self.decision_history else []

    def update_agent_performance(
        self,
        agent_name: str,
        tokens_used: int,
        duration: float,
        feedback_generated: int,
    ):
        """
        Update agent performance metrics for adaptive learning

        This should be called by agents after each execution
        Allows resource controller to learn which agents provide most value
        """
        self.optimizer.update_agent_performance(agent_name, tokens_used, duration, feedback_generated)

    def get_model_override(self, agent_name: str) -> str | None:
        """
        Get model override for an agent.
        Returns value in "endpoint/model" format if present.
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT override_model
                    FROM resource_model_overrides
                    WHERE agent_name = ?
                    ORDER BY applied_at DESC
                    LIMIT 1
                    """,
                    (agent_name,),
                )
                result = cursor.fetchone()
            return result[0] if result else None
        except Exception:
            return None

    def get_agent_statistics(self) -> dict:
        """
        Get learned agent statistics for visibility

        Shows which agents are most valuable per token spent
        """
        stats = {}

        for name, profile in self.optimizer.agent_profiles.items():
            if profile.total_calls > 0:
                stats[name] = {
                    "calls": profile.total_calls,
                    "feedback_generated": profile.total_feedback_generated,
                    "feedback_per_call": profile.total_feedback_generated / profile.total_calls,
                    "avg_tokens": int(profile.avg_tokens_per_call),
                    "avg_duration": round(profile.avg_duration_seconds, 2),
                    "value_score": round(profile.feedback_value_score, 2),
                    "tokens_per_feedback": int(
                        profile.avg_tokens_per_call
                        / max(
                            profile.total_feedback_generated / max(profile.total_calls, 1),
                            0.1,
                        )
                    ),
                }

        return stats

    def _is_throttling_disabled(self) -> bool:
        """Check if throttling is currently temporarily disabled."""
        if self.throttling_disabled_until is None:
            return False
        return datetime.now() < self.throttling_disabled_until

    def temporarily_disable_throttling(self, duration_seconds: int = 30):
        """
        Temporarily disable resource throttling for a short period.

        This is useful when we want background agents to run aggressively
        for one cycle (e.g. when orchestrator yields control).
        """
        self.throttling_disabled_until = datetime.now() + timedelta(seconds=duration_seconds)
        print(f"    🔓 Throttling temporarily disabled for {duration_seconds} seconds")


# Global singleton
_resource_controller = None


def get_resource_controller() -> ResourceControllerWorker:
    """Get global resource controller instance"""
    global _resource_controller
    if _resource_controller is None:
        _resource_controller = ResourceControllerWorker()
    return _resource_controller
