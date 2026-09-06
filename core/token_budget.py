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


def token_cap_for_endpoint(config: dict, endpoint_name: str | None) -> int:
    """Per-endpoint cap, falling back to top-level token_budget.max_tokens_per_4h."""
    default = int((config.get("token_budget") or {}).get("max_tokens_per_4h") or 50_000_000)
    if not endpoint_name or endpoint_name == "_global":
        return default
    nested = ((config.get("endpoints") or {}).get(endpoint_name) or {}).get("token_budget") or {}
    if "max_tokens_per_4h" in nested:
        return int(nested["max_tokens_per_4h"])
    return default


class TokenBudget:
    """Track token usage over a rolling 4-hour window, optionally per endpoint."""

    def __init__(self, db_path: str, max_tokens_per_4h: int = 50000000, endpoint_name: str | None = None):
        self.db_path = db_path
        self.max_tokens = max_tokens_per_4h
        self.endpoint_name = endpoint_name
        self.usage: list[tuple[Any, Any]] = []
        self.load_from_db()

    def __del__(self):
        """Cleanup on deletion (helps with Windows file locks)"""
        pass  # All connections are closed immediately after use

    def load_from_db(self):
        """Load recent token usage from database inside 4-hour window"""
        try:
            with get_db_connection(db_path=self.db_path, checkpoint_on_close=False) as conn:
                cursor = conn.cursor()
                cutoff = (datetime.now() - timedelta(hours=4)).isoformat()
                if self.endpoint_name:
                    try:
                        cursor.execute(
                            "SELECT tokens_used, timestamp FROM token_log WHERE timestamp > ? AND endpoint_name = ?",
                            (cutoff, self.endpoint_name),
                        )
                    except Exception:
                        self.usage = []
                        return
                else:
                    cursor.execute(
                        "SELECT tokens_used, timestamp FROM token_log WHERE timestamp > ?",
                        (cutoff,),
                    )
                self.usage = [(row[1], row[0]) for row in cursor.fetchall()]
        except Exception:
            self.usage = []

    def add_usage(self, tokens: int):
        """Add token usage and persist to database"""
        timestamp = datetime.now().isoformat()
        self.usage.append((timestamp, tokens))

        cutoff = (datetime.now() - timedelta(hours=4)).isoformat()
        self.usage = [(t, tok) for t, tok in self.usage if t >= cutoff]

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

    def remaining(self) -> int:
        """Get remaining tokens"""
        return max(0, self.max_tokens - self.get_used())

    def can_spend(self, estimated_tokens: int, endpoint: str | None = None, *, quiet: bool = False) -> bool:
        """Check if we can spend tokens.

        ``endpoint`` labels the exceeded print; it does not select a different
        bucket (construct a TokenBudget keyed by endpoint.name for that).
        """
        if self.remaining() < estimated_tokens:
            if not quiet:
                label = endpoint or self.endpoint_name or "global"
                print(f"⚠️  Token budget exceeded: {format_token_budget(self.get_used(), self.max_tokens)} (endpoint={label})")
            return False
        return True

    def print_status(self):
        """Print current status"""
        used = self.get_used()
        pct = (used / self.max_tokens) * 100 if self.max_tokens else 0
        label = self.endpoint_name or "global"
        print(f"📊 Tokens: {format_token_budget(used, self.max_tokens)} ({pct:.1f}%) in last 4h (endpoint={label})")
