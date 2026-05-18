"""Track fallback statistics"""
from datetime import datetime
from typing import Dict, List
from core.db_connection import get_db_connection

def log_fallback(original_endpoint: str, fallback_endpoint: str, 
                reason: str, task_id: str, agent_name: str):
    """Log a fallback event"""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS endpoint_fallbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    task_id TEXT,
                    agent_name TEXT,
                    original_endpoint TEXT,
                    fallback_endpoint TEXT,
                    reason TEXT
                )
            """)
            
            conn.execute("""
                INSERT INTO endpoint_fallbacks
                (timestamp, task_id, agent_name, original_endpoint, fallback_endpoint, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), task_id, agent_name, 
                original_endpoint, fallback_endpoint, reason))
            
    except Exception as e:
        print(f"⚠️  Failed to log fallback: {e}")

def get_fallback_stats() -> Dict:
    """Get fallback statistics"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total fallbacks
            cursor.execute("SELECT COUNT(*) FROM endpoint_fallbacks")
            total_fallbacks = cursor.fetchone()[0]
            
            # Fallbacks by reason
            cursor.execute("""
                SELECT reason, COUNT(*) 
                FROM endpoint_fallbacks 
                GROUP BY reason
                ORDER BY COUNT(*) DESC
            """)
            by_reason = dict(cursor.fetchall())
            
            # Most affected endpoints
            cursor.execute("""
                SELECT original_endpoint, COUNT(*) 
                FROM endpoint_fallbacks 
                GROUP BY original_endpoint
                ORDER BY COUNT(*) DESC
            """)
            by_endpoint = dict(cursor.fetchall())
            
            # Recent fallbacks
            cursor.execute("""
                SELECT timestamp, agent_name, original_endpoint, fallback_endpoint, reason
                FROM endpoint_fallbacks
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            recent = cursor.fetchall()
  
        return {
            "total": total_fallbacks,
            "by_reason": by_reason,
            "by_endpoint": by_endpoint,
            "recent": recent
        }
    except:
        return {"total": 0, "by_reason": {}, "by_endpoint": {}, "recent": []}