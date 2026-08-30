"""
Reject binary payloads that must never enter governed source trees.

Edge case: constrained LLMs (e.g. Gemini) have returned Windows MSI / PE
content under full_replace. Detect **binary content**, not text languages.

Text scripts (.ps1, .bat, .cmd, .js, .vbs, etc.) are allowed when content is text.

Config (optional ``content_safety`` section in config.json)::

    "content_safety": {
      "disallow_binary_content": true,
      "blocked_extensions": [".msi", ".exe", ".dll", ...]
    }

- ``disallow_binary_content`` (bool, default true): magic/NUL/ratio checks.
- ``blocked_extensions`` (list of str): path suffixes that are refused.
  Defaults to DEFAULT_BLOCKED_EXTENSIONS when omitted.
  Set to ``[]`` to disable extension-based blocking entirely.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

# Default path suffixes refused by extension check (binary containers only).
# Override via content_safety.blocked_extensions in config.json.
DEFAULT_BLOCKED_EXTENSIONS = frozenset(
    {
        ".msi",
        ".msp",
        ".msm",
        ".msu",
        ".exe",
        ".dll",
        ".sys",
        ".com",
        ".scr",
        ".cpl",
        ".ocx",
        ".drv",
        ".bin",
        ".iso",
        ".img",
        ".dmg",
        ".appx",
        ".appxbundle",
        ".msix",
        ".cab",
    }
)

# Kept as alias for tests/docs that import the name
BLOCKED_BINARY_EXTENSIONS = DEFAULT_BLOCKED_EXTENSIONS

_MAGIC_PREFIXES = (
    (b"MZ", "PE/DOS executable"),
    (b"\x7fELF", "ELF binary"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "OLE/CFB compound (often MSI/Office binary)"),
    (b"\xfe\xed\xfa", "Mach-O binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O binary"),
    (b"\xcf\xfa\xed\xfe", "Mach-O binary"),
)


def _normalize_ext(ext: str) -> str:
    e = str(ext).strip().lower().replace("\\", "/")
    if not e:
        return ""
    if not e.startswith("."):
        e = "." + e
    # Already dot-prefixed (or empty) at this point.
    return e


def get_content_safety_settings(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read content_safety flags; safe defaults if config missing."""
    if config is None:
        try:
            from core.config import get_config

            config = get_config()
        except Exception:
            config = {}
    cs = (config or {}).get("content_safety") or {}
    if not isinstance(cs, dict):
        cs = {}

    disallow = bool(cs.get("disallow_binary_content", True))

    if "blocked_extensions" in cs:
        raw = cs.get("blocked_extensions")
        blocked: set[str] = set()
        if isinstance(raw, (list, tuple)):
            for item in raw:
                ne = _normalize_ext(item)
                if ne:
                    blocked.add(ne)
        # explicit [] means no extension blocking
    else:
        blocked = set(DEFAULT_BLOCKED_EXTENSIONS)

    return {
        "disallow_binary_content": disallow,
        "blocked_extensions": frozenset(blocked),
    }


def _as_bytes_sample(content: str | bytes | list, max_bytes: int = 8192) -> bytes:
    if content is None:
        return b""
    if isinstance(content, bytes):
        return content[:max_bytes]
    if isinstance(content, list):
        text = "\n".join("" if c is None else str(c) for c in content)
    else:
        text = str(content)
    return text.encode("utf-8", errors="surrogateescape")[:max_bytes]


def looks_like_binary(content: str | bytes | list) -> tuple[bool, str]:
    """Heuristic binary detection. Returns (is_binary, reason)."""
    sample = _as_bytes_sample(content)
    if not sample:
        return False, ""

    for magic, label in _MAGIC_PREFIXES:
        if sample.startswith(magic):
            return True, f"binary magic: {label}"

    if b"\x00" in sample:
        return True, "NUL byte in content (binary)"

    if len(sample) >= 64:
        nontext = 0
        for b in sample:
            if b in (9, 10, 13):
                continue
            if b < 32 or b == 127:
                nontext += 1
        if nontext / len(sample) > 0.30:
            return True, f"high non-text byte ratio ({nontext}/{len(sample)})"

    return False, ""


def path_has_blocked_extension(
    file_path: str | None,
    blocked: frozenset[str] | set[str],
) -> tuple[bool, str]:
    """True if path uses an extension in the blocked list."""
    if not file_path or not blocked:
        return False, ""
    name = str(file_path).replace("\\", "/").lower()
    suffix = PurePosixPath(name).suffix
    if suffix in blocked:
        return True, f"blocked extension {suffix}"
    for ext in blocked:
        if name.endswith(ext):
            return True, f"blocked extension ending with {ext}"
    return False, ""


def validate_source_content(
    content: str | bytes | list | None,
    *,
    file_path: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fail-closed for binary payloads (defaults).

    Extension blocking uses ``content_safety.blocked_extensions`` only
    (no separate allow-list / exception logic).
    """
    settings = get_content_safety_settings(config)
    blocked = settings["blocked_extensions"]

    is_blocked, reason = path_has_blocked_extension(file_path, blocked)
    if is_blocked:
        return {
            "ok": False,
            "message": (
                f"Refusing path {file_path!r}: {reason}. Remove it from content_safety.blocked_extensions to allow this path (content checks may still apply)."
            ),
        }

    if content is None:
        return {"ok": True}

    if settings["disallow_binary_content"]:
        is_bin, bin_reason = looks_like_binary(content)
        if is_bin:
            return {
                "ok": False,
                "message": (
                    f"Refusing binary payload for {file_path or 'file'}: {bin_reason}. "
                    "Governed edits must be text source only (never MSI/EXE/PE/OLE binaries). "
                    "Set content_safety.disallow_binary_content false only if you accept that risk."
                ),
            }

    return {"ok": True}
