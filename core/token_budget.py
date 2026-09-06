"""Token budget tracking"""

from datetime import datetime, timedelta
from typing import Any

from core.db_connection import get_db_connection


def _fmt_tokens(n: int) -> str:
    n = int(n)
    if abs(n) >= 1_000_000:
        text = f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{text}M"
    if abs(n) >= 1_000:
        text = f"{n / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{text}k"
    return str(n)


def format_token_budget(used: int, cap: int) -> str:
    """Human-readable used/cap. Never a bare ``0M / 0M``."""
    return f"{_fmt_tokens(used)} / {_fmt_tokens(cap)}"


def _endpoint_token_budget(config: dict, endpoint_name: str | None) -> dict:
    if not endpoint_name or endpoint_name == "_global":
        return {}
    return ((config.get("endpoints") or {}).get(endpoint_name) or {}).get("token_budget") or {}


def token_cap_for_endpoint(config: dict, endpoint_name: str | None) -> int:
    """Per-endpoint 4h cap, falling back to top-level token_budget.max_tokens_per_4h."""
    default = int((config.get("token_budget") or {}).get("max_tokens_per_4h") or 50_000_000)
    nested = _endpoint_token_budget(config, endpoint_name)
    if "max_tokens_per_4h" in nested:
        return int(nested["max_tokens_per_4h"])
    return default


def token_daily_cap_for_endpoint(config: dict, endpoint_name: str | None) -> int | None:
    """Per-endpoint daily cap, falling back to top-level token_budget.max_tokens_per_day.

    ``None`` means no daily gate on this bucket (resource_controller may still
    apply its own process-wide max_tokens_per_day).
    """
    nested = _endpoint_token_budget(config, endpoint_name)
    if "max_tokens_per_day" in nested:
        return int(nested["max_tokens_per_day"])
    top = (config.get("token_budget") or {}).get("max_tokens_per_day")
    if top is None:
        return None
    return int(top)


class TokenBudget:
    """Track token usage over rolling 4-hour and optional 24-hour windows, per endpoint."""

    def __init__(
        self,
        db_path: str,
        max_tokens_per_4h: int = 50000000,
        endpoint_name: str | None = None,
        max_tokens_per_day: int | None = None,
    ):
        self.db_path = db_path
        self.max_tokens = max_tokens_per_4h
        self.max_tokens_per_day = max_tokens_per_day
        self.endpoint_name = endpoint_name
        self.usage: list[tuple[Any, Any]] = []
        self.usage_day: list[tuple[Any, Any]] = []
        self.load_from_db()

    def __del__(self):
        """Cleanup on deletion (helps with Windows file locks)"""
        pass  # All connections are closed immediately after use

    def load_from_db(self):
        """Load recent token usage from database (24h, then derive the 4h window)."""
        try:
            with get_db_connection(db_path=self.db_path, checkpoint_on_close=False) as conn:
                cursor = conn.cursor()
                cutoff_day = (datetime.now() - timedelta(hours=24)).isoformat()
                cutoff_4h = (datetime.now() - timedelta(hours=4)).isoformat()
                if self.endpoint_name:
                    try:
                        cursor.execute(
                            "SELECT tokens_used, timestamp FROM token_log WHERE timestamp > ? AND endpoint_name = ?",
                            (cutoff_day, self.endpoint_name),
                        )
                    except Exception:
                        self.usage = []
                        self.usage_day = []
                        return
                else:
                    cursor.execute(
                        "SELECT tokens_used, timestamp FROM token_log WHERE timestamp > ?",
                        (cutoff_day,),
                    )
                rows = [(row[1], row[0]) for row in cursor.fetchall()]
                self.usage_day = rows
                self.usage = [(t, tok) for t, tok in rows if t >= cutoff_4h]
        except Exception:
            self.usage = []
            self.usage_day = []

    def add_usage(self, tokens: int):
        """Add token usage and persist to database"""
        timestamp = datetime.now().isoformat()
        self.usage.append((timestamp, tokens))
        self.usage_day.append((timestamp, tokens))

        cutoff_4h = (datetime.now() - timedelta(hours=4)).isoformat()
        cutoff_day = (datetime.now() - timedelta(hours=24)).isoformat()
        self.usage = [(t, tok) for t, tok in self.usage if t >= cutoff_4h]
        self.usage_day = [(t, tok) for t, tok in self.usage_day if t >= cutoff_day]

        try:
            with get_db_connection(db_path=self.db_path, checkpoint_on_close=False) as conn:
                try:
                    conn.execute(
                        "INSERT INTO token_log (timestamp, tokens_used, endpoint_name) VALUES (?, ?, ?)",
                        (timestamp, tokens, self.endpoint_name),
                    )
                except Exception:
                    conn.execute(
                        "INSERT INTO token_log (timestamp, tokens_used) VALUES (?, ?)",
                        (timestamp, tokens),
                    )
        except Exception as e:
            print(f"    ⚠️  Exception handled in token_budget.py: {e}")

    def get_used(self) -> int:
        """Get tokens used in last 4 hours"""
        return sum(tok for _, tok in self.usage)

    def get_used_day(self) -> int:
        """Get tokens used in last 24 hours"""
        return sum(tok for _, tok in self.usage_day)

    def remaining(self) -> int:
        """Get remaining tokens in the 4h window"""
        return max(0, self.max_tokens - self.get_used())

    def remaining_day(self) -> int | None:
        """Get remaining tokens in the 24h window, or None if no daily cap."""
        if self.max_tokens_per_day is None:
            return None
        return max(0, int(self.max_tokens_per_day) - self.get_used_day())

    def can_spend(self, estimated_tokens: int, endpoint: str | None = None, *, quiet: bool = False) -> bool:
        """Check if we can spend tokens.

        ``endpoint`` labels the exceeded print; it does not select a different
        bucket (construct a TokenBudget keyed by endpoint.name for that).
        """
        label = endpoint or self.endpoint_name or "global"
        if self.remaining() < estimated_tokens:
            if not quiet:
                print(f"⚠️  Token budget exceeded: {format_token_budget(self.get_used(), self.max_tokens)} (endpoint={label}, window=4h)")
            return False
        day_left = self.remaining_day()
        if day_left is not None and day_left < estimated_tokens:
            if not quiet:
                print(
                    f"⚠️  Token budget exceeded: {format_token_budget(self.get_used_day(), int(self.max_tokens_per_day or 0))} (endpoint={label}, window=24h)"
                )
            return False
        return True

    def print_status(self):
        """Print current 4h and daily status"""
        used = self.get_used()
        pct = (used / self.max_tokens) * 100 if self.max_tokens else 0
        label = self.endpoint_name or "global"
        print(f"📊 Tokens: {format_token_budget(used, self.max_tokens)} ({pct:.1f}%) in last 4h (endpoint={label})")
        if self.max_tokens_per_day is not None:
            used_day = self.get_used_day()
            pct_day = (used_day / self.max_tokens_per_day) * 100 if self.max_tokens_per_day else 0
            print(f"📊 Tokens: {format_token_budget(used_day, self.max_tokens_per_day)} ({pct_day:.1f}%) in last 24h (endpoint={label})")
