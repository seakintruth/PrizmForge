"""Context archival helpers"""
from datetime import datetime
from core.db_connection import get_db_connection

def archive_raw_response(task_id: str, agent_name: str, prompt: str, 
                        response: str, parse_success: bool, 
                        parse_error: str = None):
    """Archive raw agent response for debugging"""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO agent_responses_archive
                (task_id, agent_name, prompt, response, parse_success, parse_error, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, agent_name, prompt, response, 
                1 if parse_success else 0, parse_error, 
                datetime.now().isoformat()))
    except Exception as e:
        print(f"⚠️  Failed to archive response: {e}")