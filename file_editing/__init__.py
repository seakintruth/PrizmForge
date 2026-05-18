# =============================================================================
# PrizmForge/file_editing/__init__.py
# Version: 1.3 - Removed broken proposal import
# Purpose: Governed, database-backed file editing subsystem for PrizmForge
# =============================================================================

from .edit_payload import EditPayload
from .db import (
    get_db_connection, 
    log_error, 
    initialize_database,
    reconstruct_file_content,
    capture_current_hashes
)
from .editing import apply_edit_proposal, validate_proposal
from .writer import materialize_proposal, write_file_to_disk, invalidate_other_proposals

__version__ = "1.3"

__all__ = [
    "EditPayload",
    "get_db_connection",
    "log_error",
    "initialize_database",
    "reconstruct_file_content",
    "capture_current_hashes",
    "apply_edit_proposal",
    "validate_proposal",
    "materialize_proposal",
    "write_file_to_disk",
    "invalidate_other_proposals",
]
