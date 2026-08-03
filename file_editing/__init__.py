# =============================================================================
# PrizmForge/file_editing/__init__.py
# Version: 1.3 - Removed broken proposal import
# Purpose: Governed, database-backed file editing subsystem for PrizmForge
# =============================================================================

from .db import capture_current_hashes, get_db_connection, initialize_database, log_error, reconstruct_file_content
from .edit_payload import EditPayload
from .editing import apply_edit_proposal, validate_proposal
from .writer import initialize_file_lines, invalidate_other_proposals, materialize_proposal, write_file_to_disk

__version__ = "1.4"

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
    "initialize_file_lines",
]
