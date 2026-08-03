"""
Edit mode selection and fallback policy.

Chooses an initial edit mode using simple t-shirt-size heuristics
(file size + change complexity) and provides an ordered fallback chain
when the primary mode fails validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

# Canonical mode names used across the system
MODE_GUID = "guid"
MODE_DIFF = "diff"
MODE_FIND_REPLACE = "find_replace"
MODE_FULL_REPLACE = "full_replace"

ALL_MODES = (MODE_GUID, MODE_DIFF, MODE_FIND_REPLACE, MODE_FULL_REPLACE)

# Default ordered fallback chain (highest fidelity → most reliable under LLM constraints)
DEFAULT_FALLBACK_ORDER: List[str] = [
    MODE_GUID,
    MODE_DIFF,
    MODE_FIND_REPLACE,
    MODE_FULL_REPLACE,
]


@dataclass
class ModeDecision:
    """Result of mode selection."""

    selected_mode: str
    reason: str
    fallback_chain: List[str]
    file_lines: Optional[int] = None
    change_hint: Optional[str] = None  # "small" | "medium" | "large" | None


def _estimate_change_size(instructions: str = "", files_needed: Optional[Sequence[str]] = None) -> str:
    """
    Very lightweight heuristic for change complexity.
    Returns 'small' | 'medium' | 'large'.
    """
    text = (instructions or "").lower()
    n_files = len(files_needed or [])

    # Strong signals for small, localized changes
    small_signals = (
        "rename",
        "typo",
        "fix typo",
        "string",
        "constant",
        "replace",
        "find and replace",
        "one line",
        "single line",
        "comment",
        "docstring only",
    )
    large_signals = (
        "refactor",
        "rewrite",
        "redesign",
        "migrate",
        "overhaul",
        "multiple files",
        "across the codebase",
        "architecture",
    )

    if any(s in text for s in large_signals) or n_files >= 3:
        return "large"
    if any(s in text for s in small_signals) or n_files <= 1:
        # Default lean toward small when signals are mixed or absent
        if any(s in text for s in small_signals):
            return "small"
    return "medium"


def select_edit_mode(
    file_line_count: Optional[int] = None,
    instructions: str = "",
    files_needed: Optional[Sequence[str]] = None,
    preferred_modes: Optional[Sequence[str]] = None,
    fallback_order: Optional[Sequence[str]] = None,
    small_file_threshold_lines: int = 180,
) -> ModeDecision:
    """
    Choose the initial edit mode using t-shirt sizing.

    Rules (deterministic, easy to reason about):
    - Very small files → prefer full_replace
    - Small / localized changes → prefer find_replace
    - Large or multi-file / complex changes → prefer guid
    - Otherwise fall through the configured preference list
    """
    chain = list(fallback_order or DEFAULT_FALLBACK_ORDER)
    # Keep only known modes and preserve order
    chain = [m for m in chain if m in ALL_MODES]
    if not chain:
        chain = list(DEFAULT_FALLBACK_ORDER)

    change_hint = _estimate_change_size(instructions, files_needed)
    lines = file_line_count if file_line_count is not None else None

    # 1. Tiny files → full replace is simplest and most reliable
    if lines is not None and lines <= small_file_threshold_lines // 3:  # ~60 lines
        return ModeDecision(
            selected_mode=MODE_FULL_REPLACE,
            reason=f"File is very small ({lines} lines); full_replace is most reliable",
            fallback_chain=chain,
            file_lines=lines,
            change_hint=change_hint,
        )

    # 2. Small / localized textual change → find_replace
    if change_hint == "small":
        return ModeDecision(
            selected_mode=MODE_FIND_REPLACE,
            reason="Change appears small/localized; find_replace preferred for LLM reliability",
            fallback_chain=chain,
            file_lines=lines,
            change_hint=change_hint,
        )

    # 3. Small-ish files with medium change still benefit from find_replace or full_replace
    if lines is not None and lines <= small_file_threshold_lines:
        if change_hint == "medium":
            return ModeDecision(
                selected_mode=MODE_FIND_REPLACE,
                reason=f"File is small ({lines} lines) and change is medium; find_replace preferred",
                fallback_chain=chain,
                file_lines=lines,
                change_hint=change_hint,
            )

    # 4. Complex / large → GUID
    if change_hint == "large":
        return ModeDecision(
            selected_mode=MODE_GUID,
            reason="Change appears large/complex; GUID mode preferred for precision",
            fallback_chain=chain,
            file_lines=lines,
            change_hint=change_hint,
        )

    # 5. Honour explicit preferred_modes if provided
    if preferred_modes:
        for m in preferred_modes:
            if m in ALL_MODES:
                return ModeDecision(
                    selected_mode=m,
                    reason=f"Using configured preferred mode '{m}'",
                    fallback_chain=chain,
                    file_lines=lines,
                    change_hint=change_hint,
                )

    # 6. Default: first item in fallback chain (normally guid)
    return ModeDecision(
        selected_mode=chain[0],
        reason=f"Default selection from fallback chain ({chain[0]})",
        fallback_chain=chain,
        file_lines=lines,
        change_hint=change_hint,
    )


def next_fallback_mode(
    current_mode: str,
    fallback_chain: Optional[Sequence[str]] = None,
    already_tried: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """
    Return the next mode to try after a failure of current_mode.
    Returns None when the chain is exhausted.
    """
    chain = list(fallback_chain or DEFAULT_FALLBACK_ORDER)
    tried = set(already_tried or [])
    tried.add(current_mode)

    for mode in chain:
        if mode not in tried and mode in ALL_MODES:
            return mode
    return None


def build_developer_edit_prompt(
    mode: str,
    understanding: str,
    files_content: List[str],
) -> str:
    """
    Build the JSON-generation prompt for a given edit mode.
    Shared by the primary attempt and any automatic fallback retries.
    """
    joined = "\n".join(files_content)

    if mode == MODE_FULL_REPLACE:
        schema = """{
  "target_file_path": "path/to/file.py",
  "new_content": "def hello():\\n    print('world')\\n    return True",
  "summary": "Updated hello function",
  "rationale": "Improved implementation as requested"
}"""
        return f"""Based on your analysis:
{understanding}

**CURRENT FILES:**

{joined}

**EDIT METHOD: FULL REPLACE**

Provide the ENTIRE new file content after your changes.

**Required JSON structure:**
{schema}

**CRITICAL:**
- new_content must contain the COMPLETE file (all lines, including unchanged ones)
- Use \\n for newlines within the string
- Escape quotes as \\"
- First character: {{
- Last character: }}
- NO markdown fences

START YOUR JSON OUTPUT NOW:"""

    if mode == MODE_DIFF:
        schema = """{
  "target_file_path": "path/to/file.py",
  "diff": "--- a/path/to/file.py\\n+++ b/path/to/file.py\\n@@ -1,3 +1,3 @@\\n def hello():\\n-    print('old')\\n+    print('new')\\n     return True",
  "summary": "Updated print statement",
  "rationale": "Changed output message"
}"""
        return f"""Based on your analysis:
{understanding}

**CURRENT FILES:**

{joined}

**EDIT METHOD: PLANNED DIFF**

Provide a unified diff showing your changes.

**Required JSON structure:**
{schema}

**CRITICAL:**
- diff must be in unified diff format
- Use \\n for newlines within the string
- First character: {{
- Last character: }}
- NO markdown fences

START YOUR JSON OUTPUT NOW:"""

    if mode == MODE_FIND_REPLACE:
        schema = """{
  "target_file_path": "path/to/file.py",
  "summary": "Rename identifier",
  "rationale": "Consistent naming",
  "operations": [
    {
      "type": "find_replace",
      "find": "old_name",
      "replace": "new_name",
      "regex": false,
      "count": null,
      "rationale": "Rename old_name to new_name"
    }
  ]
}"""
        return f"""Based on your analysis:
{understanding}

**CURRENT FILES:**

{joined}

**EDIT METHOD: FIND / REPLACE**

Prefer simple, exact textual replacements. You may emit one or more find_replace operations.

**Required JSON structure:**
{schema}

**CRITICAL:**
- Output ONLY valid JSON
- First character: {{
- Last character: }}
- NO markdown fences
- Use exact strings unless regex is truly required

START YOUR JSON OUTPUT NOW:"""

    # Default: GUID / governed operations
    schema = ""
    try:
        import json as json_lib
        from pathlib import Path

        schema_file = Path(__file__).parent.parent / "agent_schemas" / "developer.json"
        if schema_file.exists():
            with open(schema_file) as f:
                schema = json_lib.dumps(json_lib.load(f), indent=2)
    except Exception:
        schema = '{"target_file_path": "...", "summary": "...", "operations": [], "rationale": "..."}'

    return f"""Based on your analysis:
{understanding}

Convert your plan into the required JSON EditPayload format.

**Files with line_guids:**

{joined}

**EDIT METHOD: GUID SLOC (Governed Editing)**

You may also use find_replace operations when a simple textual change is sufficient.

**Required JSON structure:**
{schema}

**CRITICAL RULES:**
1. Your ENTIRE response must be ONLY valid JSON
2. First character must be {{
3. Last character must be }}
4. NO markdown fences (```json)
5. NO explanatory text
6. Use the actual line_guids shown above (for GUID ops) or find/replace strings

START YOUR JSON OUTPUT NOW:"""
