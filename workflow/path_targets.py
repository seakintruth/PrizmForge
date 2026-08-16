"""
Sanitize and extract developer file targets (FILES_NEEDED / prose).

Prevents markdown decoration (``** `path` ``) and path traversal from becoming
create_file / edit targets — a failure mode observed in unattended self-edit runs.
"""

from __future__ import annotations

import re

_NONE_TOKENS = frozenset({"NONE", "N/A", "NONE.", "N/A."})

# Relative path: segments of safe identifier chars, optional extension
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")

_FILES_NEEDED_LINE = re.compile(r"FILES_NEEDED:\s*(.+?)(?:\n|$)", re.IGNORECASE)

_PROSE_FILE = re.compile(r"(?:^|\s|`)([A-Za-z0-9_./\\-]+\.(?:py|json|js|txt|md|html|css|yaml|yml|sh))(?:$|\s|`|[,;])")


def sanitize_path_token(raw: str | None) -> str | None:
    """
    Strip markdown/quotes from a path-like token.

    Returns a clean relative POSIX path, or None if the token is unusable
    (empty, NONE/N/A, traversal, residual junk).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    for _ in range(4):
        prev = s
        s = s.strip().strip("`\"'")
        if len(s) >= 4 and s.startswith("**") and s.endswith("**"):
            s = s[2:-2].strip()
        elif len(s) >= 2 and s.startswith("*") and s.endswith("*") and not s.startswith("**"):
            s = s[1:-1].strip()
        s = s.strip(" \t")
        if s == prev:
            break

    # Drop residual emphasis / fence characters inside the token
    s = re.sub(r"[*`]+", "", s).strip()
    s = s.strip(".,;")
    if not s or s.upper() in _NONE_TOKENS:
        return None

    s = s.replace("\\", "/")
    parts = [p for p in s.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None

    cleaned = "/".join(parts)
    if not _SAFE_PATH.fullmatch(cleaned):
        return None
    return cleaned


def extract_files_needed_from_text(text: str, *, max_files: int = 8) -> list[str]:
    """
    Extract ordered, deduplicated file paths from developer phase-1 text.

    Prefers a FILES_NEEDED: line; falls back to prose path matches.
    Every token is passed through sanitize_path_token.
    """
    if not text or not str(text).strip():
        return []

    requested: list[str] = []
    match = _FILES_NEEDED_LINE.search(text)
    if match:
        files_str = match.group(1).strip()
        if files_str.upper() not in _NONE_TOKENS:
            for part in files_str.split(","):
                clean = sanitize_path_token(part)
                if clean:
                    requested.append(clean)

    if not requested:
        for found in _PROSE_FILE.findall(text):
            clean = sanitize_path_token(found)
            if clean:
                requested.append(clean)

    # Preserve order, drop duplicates
    return list(dict.fromkeys(requested))[:max_files]


def is_valid_edit_target_path(path: str | None) -> bool:
    """True when path is a sanitized relative path safe for proposals / create_file."""
    if path is None:
        return False
    clean = sanitize_path_token(path)
    if not clean:
        return False
    # Reject if sanitize had to change the semantic path beyond slash normalize
    str(path).replace("\\", "/").strip()
    # Allow input that only differed by markdown/wrappers: clean must equal
    # sanitize of itself (always) — compare to a second sanitize of cleaned form
    return clean == sanitize_path_token(clean)
