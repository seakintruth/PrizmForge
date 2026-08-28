# file_editing/edit_payload.py
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal


def _validate_target_path(path: str | None, *, field_name: str = "target_file_path") -> str:
    """
    Require a clean relative path (no markdown decoration or traversal).

    Decorated tokens are accepted upstream via sanitize in FILES_NEEDED extraction;
    at the EditPayload boundary the path must already be clean so junk does not
    enter proposals.
    """
    from workflow.path_targets import sanitize_path_token

    if not isinstance(path, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = sanitize_path_token(path)
    if not cleaned:
        raise ValueError(f"{field_name} is not a valid relative path: {path!r}")
    normalized = path.replace("\\", "/").strip()
    if normalized != cleaned:
        raise ValueError(f"{field_name} is not a valid relative path: {path!r}")
    return cleaned


# kw_only=True on all dataclasses to fix inheritance ordering issues
@dataclass(kw_only=True)
class BaseOperation:
    type: str
    target_file_path: str | None = None
    rationale: str = "Change as specified"

    def __post_init__(self):
        # Pydantic-like Type Validation
        if not isinstance(self.rationale, str):
            raise ValueError("rationale must be a string")

        # Auto-expand too-short rationales
        if len(self.rationale) < 10:
            self.rationale = f"{self.rationale} (applied as specified in task)"

        # Auto-truncate overly long rationales instead of rejecting the whole
        # edit: rationale is audit metadata, not load-bearing content. LLMs
        # routinely exceed soft limits and a hard error here kills valid edits.
        if len(self.rationale) > 3200:
            self.rationale = self.rationale[:3197] + "..."

        if self.target_file_path is not None:
            self.target_file_path = _validate_target_path(self.target_file_path)


@dataclass(kw_only=True)
class ReplaceBlock(BaseOperation):
    start_line_guid: str
    end_line_guid: str | None = None
    new_content: list[str] = field(default_factory=list)
    type: Literal["replace_block"] = "replace_block"

    def __post_init__(self):
        super().__post_init__()
        # Pydantic-like Auto-Coercion: LLMs often output a string instead of a list of strings
        if isinstance(self.new_content, str):
            self.new_content = [self.new_content]
        elif not isinstance(self.new_content, list):
            raise ValueError("new_content must be a list of strings")


@dataclass(kw_only=True)
class InsertAfter(BaseOperation):
    after_guid: str | None = None
    new_content: list[str] = field(default_factory=list)
    type: Literal["insert_after"] = "insert_after"

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.new_content, str):
            self.new_content = [self.new_content]
        elif not isinstance(self.new_content, list):
            raise ValueError("new_content must be a list of strings")


@dataclass(kw_only=True)
class DeleteLines(BaseOperation):
    start_line_guid: str
    end_line_guid: str | None = None
    type: Literal["delete_lines"] = "delete_lines"


@dataclass(kw_only=True)
class UpdateDocumentation(BaseOperation):
    new_content: str
    type: Literal["update_documentation"] = "update_documentation"

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.new_content, str):
            raise ValueError("new_content must be a string for update_documentation")


@dataclass(kw_only=True)
class CreateFile(BaseOperation):
    target_file_path: str
    initial_content: list[str] = field(default_factory=list)
    type: Literal["create_file"] = "create_file"

    def __post_init__(self):
        super().__post_init__()
        self.target_file_path = _validate_target_path(self.target_file_path)
        if isinstance(self.initial_content, str):
            self.initial_content = [self.initial_content]


@dataclass(kw_only=True)
class DeleteFile(BaseOperation):
    """Governed whole-file deletion (mini-swe §4: the previously missing delete op).

    Flips the governed store row + lines to is_deleted=1; materialize removes
    the disk file and stages the deletion for commit.
    """

    target_file_path: str
    type: Literal["delete_file"] = "delete_file"

    def __post_init__(self):
        super().__post_init__()
        self.target_file_path = _validate_target_path(self.target_file_path)


@dataclass(kw_only=True)
class FindReplace(BaseOperation):
    """Simple find-and-replace operation. Preferred fallback under LLM constraints."""

    find: str
    replace: str
    regex: bool = False
    count: int | None = None  # None = replace all
    type: Literal["find_replace"] = "find_replace"

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.find, str) or not self.find:
            raise ValueError("find must be a non-empty string")
        if not isinstance(self.replace, str):
            raise ValueError("replace must be a string")
        if self.count is not None and (not isinstance(self.count, int) or self.count < 0):
            raise ValueError("count must be None or a non-negative integer")


@dataclass(kw_only=True)
class FullReplace(BaseOperation):
    """Replace the entire file content. Preferred for very small files."""

    new_content: str
    type: Literal["full_replace"] = "full_replace"

    def __post_init__(self):
        super().__post_init__()
        # Accept list of lines from LLMs and join them
        if isinstance(self.new_content, list):
            self.new_content = "\n".join(str(line) for line in self.new_content)
            if self.new_content and not self.new_content.endswith("\n"):
                # Preserve trailing newline convention for full-file content
                pass
        if not isinstance(self.new_content, str):
            raise ValueError("new_content must be a string (or list of lines)")
        if not self.new_content.strip():
            raise ValueError("new_content must not be empty")


@dataclass(kw_only=True)
class ApplyDiff(BaseOperation):
    """Apply a unified diff to the file content."""

    diff: str
    type: Literal["apply_diff"] = "apply_diff"

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.diff, str) or not self.diff.strip():
            raise ValueError("diff must be a non-empty string")


Operation = ReplaceBlock | InsertAfter | DeleteLines | UpdateDocumentation | CreateFile | DeleteFile | FindReplace | FullReplace | ApplyDiff

#: Canonical operation types accepted by EditPayload. Shared by the developer
#: validator (Workstream D: "one schema, two gates") so an edit cannot be
#: declared valid here and then rejected by proposal_builder.
KNOWN_OPERATION_TYPES = frozenset(
    {
        "replace_block",
        "insert_after",
        "delete_lines",
        "update_documentation",
        "create_file",
        "delete_file",
        "find_replace",
        "full_replace",
        "apply_diff",
    }
)


def _req_str(op: Any, key: str) -> str | None:
    value = op.get(key)
    if not isinstance(value, str) or not value.strip():
        return f"operation requires a non-empty '{key}' string"
    return None


def _req_any(op: Any, key: str) -> str | None:
    if not isinstance(op.get(key), str) or not op.get(key):
        return f"operation requires '{key}'"
    return None


def _validate_find_replace(op: Any) -> str | None:
    if not isinstance(op.get("find"), str) or not op.get("find").strip():
        return "find_replace operation requires a non-empty 'find' string"
    if not isinstance(op.get("replace"), str):
        return "find_replace operation requires a 'replace' string"
    return None


def _validate_full_replace(op: Any) -> str | None:
    content = op.get("new_content")
    ok = isinstance(content, str) and bool(content.strip())
    ok = ok or (isinstance(content, list) and bool(content) and all(isinstance(c, str) for c in content))
    if not ok:
        return "full_replace operation requires non-empty 'new_content'"
    return None


#: Per-type required-field checks, mirroring the dataclass rules in this
#: module, used by both the developer validator and proposal_builder.
_OPERATION_CHECKS: dict[str, Callable[[Any], str | None]] = {
    "replace_block": lambda op: _req_any(op, "start_line_guid"),
    "insert_after": lambda op: None,
    "delete_lines": lambda op: _req_any(op, "start_line_guid"),
    "update_documentation": lambda op: _req_str(op, "new_content"),
    "create_file": lambda op: _req_any(op, "target_file_path"),
    "delete_file": lambda op: _req_any(op, "target_file_path"),
    "find_replace": _validate_find_replace,
    "full_replace": _validate_full_replace,
    "apply_diff": lambda op: _req_str(op, "diff"),
}


def validate_operation(op: Any) -> str | None:
    """Return an error message when an operation cannot build, else None.

    Mirrors the required-field rules enforced by the dataclasses in this
    module. Non-dict values, missing ``type``, unknown type names (e.g. the
    legacy ``guid`` mode name), and missing per-type required fields all
    produce a message so the caller can fail the payload before any proposal
    is created.
    """
    if not isinstance(op, dict):
        return "operation must be an object/dictionary"
    op_type = op.get("type")
    if not op_type:
        return "operation is missing required 'type' field"
    check = _OPERATION_CHECKS.get(op_type)
    if check is None:
        return f"unknown operation type: {op_type!r}"
    return check(op)


@dataclass(kw_only=True)
class EditPayload:
    target_file_path: str
    summary: str
    operations: list[Operation]
    rationale: str

    def __post_init__(self):
        self.target_file_path = _validate_target_path(self.target_file_path)
        if not isinstance(self.summary, str) or len(self.summary) < 5:
            raise ValueError("summary must be a string of at least 5 characters")
        if not isinstance(self.rationale, str):
            raise ValueError("rationale must be a string")
        if len(self.rationale) < 10:
            raise ValueError("rationale must be a string of at least 10 characters")
        # Same auto-truncate policy as BaseOperation: audit metadata, not
        # load-bearing content — never reject the whole edit over it.
        if len(self.rationale) > 3200:
            self.rationale = self.rationale[:3197] + "..."
        if not isinstance(self.operations, list):
            raise ValueError("operations must be a list")

    # ==========================================
    # Pydantic V2 Interface Shims
    # ==========================================
    @classmethod
    def model_validate_json(cls, json_str: str) -> "EditPayload":
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("JSON must resolve to an object/dictionary at the root level")

        return cls.model_validate(data)

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "EditPayload":  # noqa: C901
        ops = []
        for i, op_data in enumerate(data.get("operations", [])):
            if not isinstance(op_data, dict):
                raise ValueError(f"Operation at index {i} must be an object/dictionary")

            op_type = op_data.get("type")
            if not op_type:
                raise ValueError(f"Operation at index {i} is missing required 'type' field")

            try:
                op_kwargs = {k: v for k, v in op_data.items()}

                # Auto-add rationale if missing
                if "rationale" not in op_kwargs or not op_kwargs.get("rationale"):
                    if op_type == "replace_block":
                        op_kwargs["rationale"] = "Replace code block"
                    elif op_type == "insert_after":
                        op_kwargs["rationale"] = "Insert new code"
                    elif op_type == "delete_lines":
                        op_kwargs["rationale"] = "Remove lines"
                    elif op_type == "update_documentation":
                        op_kwargs["rationale"] = "Update documentation"
                    elif op_type == "create_file":
                        op_kwargs["rationale"] = "Create new file"
                    elif op_type == "delete_file":
                        op_kwargs["rationale"] = "Delete file"
                    elif op_type == "find_replace":
                        op_kwargs["rationale"] = "Find and replace text"
                    elif op_type == "full_replace":
                        op_kwargs["rationale"] = "Replace entire file content"
                    else:
                        op_kwargs["rationale"] = "Apply change"

                # Use fields() so inherited BaseOperation members are included
                op_cls_map = {
                    "replace_block": ReplaceBlock,
                    "insert_after": InsertAfter,
                    "delete_lines": DeleteLines,
                    "update_documentation": UpdateDocumentation,
                    "create_file": CreateFile,
                    "delete_file": DeleteFile,
                    "find_replace": FindReplace,
                    "full_replace": FullReplace,
                    "apply_diff": ApplyDiff,
                }

                if op_type not in op_cls_map:
                    raise ValueError(f"Unknown operation type: '{op_type}'")

                target_cls = op_cls_map[op_type]
                valid_fields = {f.name for f in fields(target_cls)}
                ops.append(target_cls(**{k: v for k, v in op_kwargs.items() if k in valid_fields}))

            except TypeError as e:
                raise ValueError(f"Validation failed for operation '{op_type}' at index {i}: Missing required fields. ({e})") from e

        try:
            return cls(
                target_file_path=data.get("target_file_path"),
                summary=data.get("summary"),
                operations=ops,
                rationale=data.get("rationale"),
            )
        except TypeError as e:
            raise ValueError(f"Validation failed for EditPayload: Missing required top-level fields. ({e})") from e

    def model_dump_json(self) -> str:
        return json.dumps(asdict(self))
