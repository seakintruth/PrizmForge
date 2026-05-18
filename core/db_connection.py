"""Thread-safe database connection with retry logic"""
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

class DatabaseRetryError(Exception):
    """Raised when database operation fails after all retries"""
    pass

@contextmanager
def get_db_connection(
    db_path: str = None,
    retries: int = 5,
    checkpoint_on_close: bool = True
):
    """
    Get database connection with automatic commit/rollback
    
    IMPORTANT: Retry logic only applies to COMMIT and CHECKPOINT,
    not to user's queries. User code must handle query retries.
    
    Args:
        db_path: Path to database (uses get_db_path() if None)
        retries: Number of retry attempts for commit/checkpoint
        checkpoint_on_close: Force WAL checkpoint before close
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT ...")  # Handle your own retries here
        # Commit happens automatically with retry
    """
    if db_path is None:
        from core.db import get_db_path
        db_path = get_db_path()
    
    # Establish connection (no retry here - fail fast)
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        
    except sqlite3.Error as e:
        raise DatabaseRetryError(f"Failed to connect to database: {e}")
    
    try:
        # User code runs here
        yield conn
        
        # Commit with retry
        _commit_with_retry(conn, retries)
        
        # Checkpoint with retry (optional)
        if checkpoint_on_close:
            _checkpoint_with_retry(conn, retries)
            
    except Exception:
        # Rollback on any exception in user code
        try:
            conn.rollback()
        except:
            pass
        raise
        
    finally:
        # Always close connection
        try:
            conn.close()
        except:
            pass


def _commit_with_retry(conn: sqlite3.Connection, retries: int = 5):
    """Commit with exponential backoff on lock errors"""
    for attempt in range(retries):
        try:
            conn.commit()
            return  # Success
            
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            
            if "locked" in error_msg or "busy" in error_msg:
                if attempt < retries - 1:
                    # Exponential backoff with jitter
                    delay = min(0.1 * (2 ** attempt), 2.0)
                    jitter = delay * 0.2 * (0.5 - time.time() % 1)
                    time.sleep(delay + jitter)
                else:
                    # Final attempt failed
                    raise DatabaseRetryError(
                        f"Commit failed after {retries} retries: {e}"
                    )
            else:
                # Different error - don't retry
                raise


def _checkpoint_with_retry(conn: sqlite3.Connection, retries: int = 3):
    """
    Checkpoint WAL with retry (less aggressive than commit retry)
    Failures are non-fatal - WAL will checkpoint eventually
    """
    for attempt in range(retries):
        try:
            result = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            # Success (even if some pages remain)
            return
            
        except sqlite3.OperationalError:
            if attempt < retries - 1:
                time.sleep(0.1 * (attempt + 1))
            else:
                # Checkpoint failed - not critical, ignore
                pass


def execute_with_retry(
    query: str,
    params: tuple = (),
    retries: int = 5,
    fetch_mode: str = None
):
    """
    Execute a query with automatic retry on lock errors
    
    Args:
        query: SQL query
        params: Query parameters
        retries: Number of retry attempts
        fetch_mode: 'one', 'all', or None (for INSERT/UPDATE)
    
    Returns:
        Query results or None
    """
    for attempt in range(retries):
        try:
            with get_db_connection(checkpoint_on_close=False) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                if fetch_mode == 'one':
                    result = cursor.fetchone()
                elif fetch_mode == 'all':
                    result = cursor.fetchall()
                else:
                    result = None
                
                # Don't commit here - context manager handles it
                return result
                
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            
            if "locked" in error_msg or "busy" in error_msg:
                if attempt < retries - 1:
                    delay = min(0.1 * (2 ** attempt), 2.0)
                    time.sleep(delay)
                else:
                    raise DatabaseRetryError(
                        f"Query failed after {retries} retries: {e}"
                    )
            else:
                raise