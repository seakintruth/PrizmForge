# =============================================================================
# PrizmForge/file_editing/__init__.py
# Version: 1.5 - Trim obsolete package re-exports
# Purpose: Governed, database-backed file editing subsystem for PrizmForge
# =============================================================================

from .writer import initialize_file_lines

__version__ = "1.5"

__all__ = [
    "initialize_file_lines",
]
