"""Token budget tracking"""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

class TokenBudget:
    """Track token usage over time"""
    
    def __init__(self, db_path: str, max_tokens_per_4h: int = 50000000):
        self.db_path = db_path
        self.max_tokens = max_tokens_per_4h
        self.usage = []
        self.load_from_db()
    
    def load_from_db(self):
        """Load recent usage from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=4)).isoformat()
            cursor.execute(
                "SELECT tokens_used, timestamp FROM token_log WHERE timestamp > ?",
                (cutoff,)
            )
            self.usage = [(row[1], row[0]) for row in cursor.fetchall()]
            conn.close()
        except:
            self.usage = []
    
    def add_usage(self, tokens: int):
        """Add token usage"""
        timestamp = datetime.now().isoformat()
        self.usage.append((timestamp, tokens))
        
        # Remove old entries
        cutoff = (datetime.now() - timedelta(hours=4)).isoformat()
        self.usage = [(t, tok) for t, tok in self.usage if t >= cutoff]
        
        # Persist to DB
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO token_log (timestamp, tokens_used) VALUES (?, ?)",
                (timestamp, tokens)
            )
            conn.commit()
            conn.close()
        except:
            pass
    
    def get_used(self) -> int:
        """Get tokens used in last 4 hours"""
        return sum(tok for _, tok in self.usage)
    
    def remaining(self) -> int:
        """Get remaining tokens"""
        return max(0, self.max_tokens - self.get_used())
    
    def can_spend(self, estimated_tokens: int) -> bool:
        """Check if we can spend tokens"""
        if self.remaining() < estimated_tokens:
            print(f"⚠️  Token budget exceeded: {self.get_used()//1000000}M / {self.max_tokens//1000000}M")
            return False
        return True
    
    def print_status(self):
        """Print current status"""
        used = self.get_used()
        pct = (used / self.max_tokens) * 100
        print(f"📊 Tokens: {used//1000000}M / {self.max_tokens//1000000}M ({pct:.1f}%) in last 4h")