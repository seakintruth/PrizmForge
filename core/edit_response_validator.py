from typing import Dict, Optional

"""
Edit response validator – early detection of failed developer outputs.

Used by the task runner to decide whether a developer response contains a
usable edit (any supported mode) or should be treated as an edit failure
and trigger fallback / retry logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class EditFailureReason(Enum):
    EMPTY_RESPONSE = "empty_response"
    NO_JSON = "no_json"
    INVALID_JSON = "invalid_json"
    MISSING_TARGET = "missing_target"
    NO_OPERATIONS = "no_operations"
    EMPTY_OPERATIONS = "empty_operations"
    UNKNOWN_STRUCTURE = "unknown_structure"
    FULL_REPLACE_MISSING_CONTENT = "full_replace_missing_content"


@dataclass
class EditValidationResult:
    """Result of validating a developer edit response."""

    is_valid: bool
    reason: Optional[EditFailureReason] = None
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    detected_mode: Optional[str] = None  # "guid" | "find_replace" | "full_replace" | "diff" | None

    @property
    def should_fallback(self) -> bool:
        return not self.is_valid


def _extract_json_object(text: str) -> Optional[str]:
    """Best-effort extraction of a top-level JSON object from LLM output."""
    if not text or not text.strip():
        return None

    cleaned = text.strip()

    # Strip common markdown fences
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    return cleaned[start : end + 1]


def validate_developer_edit_response(response: str) -> EditValidationResult:
    """
    Classify a raw developer agent response as a usable edit or a failure.

    This is intentionally conservative: if we cannot confidently extract a
    payload that contains either operations, a find/replace, or full new
    content, we treat it as a failure so the caller can fall back.
    """
    if not response or not str(response).strip():
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.EMPTY_RESPONSE,
            message="Developer returned an empty response",
        )

    json_str = _extract_json_object(response)
    if not json_str:
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.NO_JSON,
            message="No JSON object found in developer response",
        )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.INVALID_JSON,
            message=f"JSON parse error: {e}",
        )

    if not isinstance(data, dict):
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.UNKNOWN_STRUCTURE,
            message="Root JSON value is not an object",
        )

    # --- Detect mode and validate minimum usable content ---

    # Full-file replacement
    if "new_content" in data:
        new_content = data.get("new_content")
        if new_content is None or (isinstance(new_content, str) and not new_content.strip()):
            return EditValidationResult(
                is_valid=False,
                reason=EditFailureReason.FULL_REPLACE_MISSING_CONTENT,
                message="full_replace payload is missing usable new_content",
                data=data,
                detected_mode="full_replace",
            )
        return EditValidationResult(
            is_valid=True,
            data=data,
            detected_mode="full_replace",
            message="Valid full_replace payload",
        )

    # Find / replace (single or list)
    if "find" in data and "replace" in data:
        return EditValidationResult(
            is_valid=True,
            data=data,
            detected_mode="find_replace",
            message="Valid find_replace payload",
        )

    if "replacements" in data and isinstance(data["replacements"], list) and data["replacements"]:
        return EditValidationResult(
            is_valid=True,
            data=data,
            detected_mode="find_replace",
            message="Valid find_replace (replacements list) payload",
        )

    # Diff-style
    if "diff" in data and isinstance(data["diff"], str) and data["diff"].strip():
        return EditValidationResult(
            is_valid=True,
            data=data,
            detected_mode="diff",
            message="Valid diff payload",
        )

    # GUID / operations style (current governed path)
    operations = data.get("operations")
    if operations is None:
        # Some models emit a single operation at the top level
        if data.get("type") in {
            "replace_block",
            "insert_after",
            "delete_lines",
            "find_replace",
        }:
            return EditValidationResult(
                is_valid=True,
                data=data,
                detected_mode="guid",
                message="Valid single-operation payload",
            )
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.NO_OPERATIONS,
            message="Payload has no 'operations' list and does not match other known modes",
            data=data,
        )

    if not isinstance(operations, list):
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.NO_OPERATIONS,
            message="'operations' is present but is not a list",
            data=data,
        )

    if len(operations) == 0:
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.EMPTY_OPERATIONS,
            message="'operations' list is empty – no edits proposed",
            data=data,
            detected_mode="guid",
        )

    # Basic structural check: at least one operation has a type
    has_typed_op = any(isinstance(op, dict) and op.get("type") for op in operations)
    if not has_typed_op:
        return EditValidationResult(
            is_valid=False,
            reason=EditFailureReason.UNKNOWN_STRUCTURE,
            message="operations list contains no recognizable operation objects",
            data=data,
            detected_mode="guid",
        )

    return EditValidationResult(
        is_valid=True,
        data=data,
        detected_mode="guid",
        message=f"Valid GUID/operations payload with {len(operations)} operation(s)",
    )
