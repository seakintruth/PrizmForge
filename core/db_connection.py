"""Thread-safe database connection with retry logic and wall-clock countdown."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager


class DatabaseRetryError(Exception):
    """Raised when a database operation fails after all retries / time budget.

    This exception is TERMINAL for retry loops: callers must not catch it and
    retry the same operation again, or they risk an infinite error loop.
    """


# Defaults: attempt cap + wall-clock budget (seconds)
DEFAULT_COMMIT_RETRIES = 5
DEFAULT_COMMIT_MAX_SECONDS = 15.0
DEFAULT_CHECKPOINT_RETRIES = 3
DEFAULT_CHECKPOINT_MAX_SECONDS = 3.0
DEFAULT_QUERY_RETRIES = 5
DEFAULT_QUERY_MAX_SECONDS = 10.0


def _is_lock_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


def _backoff_sleep(attempt: int, deadline: float, *, cap: float = 2.0) -> bool:
    """Sleep with exponential backoff if time remains before deadline.

    Returns True if the caller should continue retrying, False if the budget
    is exhausted (caller should raise).
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return False

    delay = min(0.1 * (2**attempt), cap, remaining)
    # Small deterministic jitter from time, clamped to remaining budget
    jitter = min(delay * 0.1, max(0.0, remaining - delay))
    sleep_for = delay + jitter
    if sleep_for > 0:
        print(f"    ⏳ DB lock: retry {attempt + 1}, sleep {sleep_for:.2f}s, budget left {max(0.0, remaining - sleep_for):.2f}s")
        time.sleep(sleep_for)
    return (deadline - time.monotonic()) > 0


@contextmanager
def get_db_connection(
    db_path: str | None = None,
    retries: int = DEFAULT_COMMIT_RETRIES,
    max_retry_seconds: float = DEFAULT_COMMIT_MAX_SECONDS,
    checkpoint_on_close: bool = True,
):
    """
    Get database connection with automatic commit/rollback.

    Retry logic applies only to COMMIT and CHECKPOINT, not to user queries.
    Retries are bounded by *both* attempt count and a wall-clock countdown
    so a persistently locked DB cannot loop forever.

    Args:
        db_path: Path to database (uses get_db_path() if None)
        retries: Max commit attempts on lock/busy
        max_retry_seconds: Hard wall-clock budget for commit retries
        checkpoint_on_close: Force WAL checkpoint before close when in WAL mode
    """
    if db_path is None:
        from core.db import get_db_path

        db_path = get_db_path()

    try:
        conn = sqlite3.connect(db_path, timeout=30.0)

        # Prefer DELETE over WAL on restrictive mounts (WAL can misbehave there)
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
        except Exception:
            try:
                conn.execute("PRAGMA journal_mode=OFF")
            except Exception as e:
                print(f"    ⚠️  Exception handled in db_connection.py: {e}")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")

    except sqlite3.Error as e:
        raise DatabaseRetryError(f"Failed to connect to database: {e}") from e

    try:
        yield conn

        _commit_with_retry(conn, retries=retries, max_retry_seconds=max_retry_seconds)

        if checkpoint_on_close:
            try:
                mode = conn.execute("PRAGMA journal_mode").fetchone()
                if mode and str(mode[0]).lower() == "wal":
                    _checkpoint_with_retry(conn)
            except Exception as e:
                print(f"    ⚠️  Exception handled in db_connection.py: {e}")

    except DatabaseRetryError:
        # Terminal — rollback if possible, then re-raise without wrapping
        try:
            conn.rollback()
        except Exception as e:
            print(f"    ⚠️  Exception handled in db_connection.py: {e}")
        raise

    except Exception:
        try:
            conn.rollback()
        except Exception as e:
            print(f"    ⚠️  Exception handled in db_connection.py: {e}")
        raise

    finally:
        try:
            conn.close()
        except Exception as e:
            print(f"    ⚠️  Exception handled in db_connection.py: {e}")


def _commit_with_retry(
    conn: sqlite3.Connection,
    retries: int = DEFAULT_COMMIT_RETRIES,
    max_retry_seconds: float = DEFAULT_COMMIT_MAX_SECONDS,
):
    """Commit with exponential backoff on lock errors + hard countdown."""
    deadline = time.monotonic() + max(0.0, max_retry_seconds)
    last_error: BaseException | None = None

    for attempt in range(max(1, retries)):
        try:
            conn.commit()
            return

        except sqlite3.OperationalError as e:
            last_error = e
            if not _is_lock_error(e):
                raise

            if attempt >= retries - 1:
                break

            if not _backoff_sleep(attempt, deadline):
                break

    raise DatabaseRetryError(f"Commit failed after {retries} attempts or {max_retry_seconds:.1f}s budget: {last_error}") from last_error


def _checkpoint_with_retry(
    conn: sqlite3.Connection,
    retries: int = DEFAULT_CHECKPOINT_RETRIES,
    max_retry_seconds: float = DEFAULT_CHECKPOINT_MAX_SECONDS,
):
    """Checkpoint WAL with short countdown. Failures are non-fatal."""
    deadline = time.monotonic() + max(0.0, max_retry_seconds)

    for attempt in range(max(1, retries)):
        try:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            return
        except sqlite3.OperationalError:
            if attempt >= retries - 1:
                return
            if not _backoff_sleep(attempt, deadline, cap=0.5):
                return


def execute_with_retry(
    query: str,
    params: tuple = (),
    retries: int = DEFAULT_QUERY_RETRIES,
    max_retry_seconds: float = DEFAULT_QUERY_MAX_SECONDS,
    fetch_mode: str | None = None,
):
    """
    Execute a query with automatic retry on lock/busy errors.

    Bounded by attempt count AND wall-clock countdown. DatabaseRetryError from
    an inner commit is re-raised immediately (not retried) to avoid nested
    infinite loops.
    """
    deadline = time.monotonic() + max(0.0, max_retry_seconds)
    last_error: BaseException | None = None

    for attempt in range(max(1, retries)):
        try:
            with get_db_connection(
                checkpoint_on_close=False,
                retries=min(3, retries),
                max_retry_seconds=min(3.0, max_retry_seconds),
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)

                if fetch_mode == "one":
                    return cursor.fetchone()
                if fetch_mode == "all":
                    return cursor.fetchall()
                return None

        except DatabaseRetryError:
            # Terminal from inner commit path — do not expand into another loop
            raise

        except sqlite3.OperationalError as e:
            last_error = e
            if not _is_lock_error(e):
                raise

            if attempt >= retries - 1:
                break

            if not _backoff_sleep(attempt, deadline):
                break

    raise DatabaseRetryError(f"Query failed after {retries} attempts or {max_retry_seconds:.1f}s budget: {last_error}") from last_error
