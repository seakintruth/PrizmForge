# file_editing/edit_payload.py
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


# ✅ ADDED kw_only=True to all dataclasses to fix inheritance ordering issues
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

        if len(self.rationale) > 500:
            raise ValueError(f"rationale must be <= 500 characters (got {len(self.rationale)})")


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
        if isinstance(self.initial_content, str):
            self.initial_content = [self.initial_content]


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


Operation = ReplaceBlock | InsertAfter | DeleteLines | UpdateDocumentation | CreateFile | FindReplace | FullReplace | ApplyDiff


@dataclass(kw_only=True)
class EditPayload:
    target_file_path: str
    summary: str
    operations: list[Operation]
    rationale: str

    def __post_init__(self):
        if not isinstance(self.target_file_path, str):
            raise ValueError("target_file_path must be a string")
        if not isinstance(self.summary, str) or len(self.summary) < 5:
            raise ValueError("summary must be a string of at least 5 characters")
        if not isinstance(self.rationale, str) or len(self.rationale) < 10:
            raise ValueError("rationale must be a string of at least 10 characters")
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

            # Pydantic-like Discriminator mapping with clean TypeError wrapping
            # Pydantic-like Discriminator mapping with auto-fix for missing rationale
            try:
                # Extract operation data and ensure rationale exists
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
                    elif op_type == "find_replace":
                        op_kwargs["rationale"] = "Find and replace text"
                    elif op_type == "full_replace":
                        op_kwargs["rationale"] = "Replace entire file content"
                    else:
                        op_kwargs["rationale"] = "Apply change"

                # Now create the operation object
                if op_type == "replace_block":
                    ops.append(ReplaceBlock(**{k: v for k, v in op_kwargs.items() if k in ReplaceBlock.__annotations__}))
                elif op_type == "insert_after":
                    ops.append(InsertAfter(**{k: v for k, v in op_kwargs.items() if k in InsertAfter.__annotations__}))
                elif op_type == "delete_lines":
                    ops.append(DeleteLines(**{k: v for k, v in op_kwargs.items() if k in DeleteLines.__annotations__}))
                elif op_type == "update_documentation":
                    ops.append(UpdateDocumentation(**{k: v for k, v in op_kwargs.items() if k in UpdateDocumentation.__annotations__}))
                elif op_type == "create_file":
                    ops.append(CreateFile(**{k: v for k, v in op_kwargs.items() if k in CreateFile.__annotations__}))
                elif op_type == "find_replace":
                    ops.append(FindReplace(**{k: v for k, v in op_kwargs.items() if k in FindReplace.__annotations__}))
                elif op_type == "full_replace":
                    ops.append(FullReplace(**{k: v for k, v in op_kwargs.items() if k in FullReplace.__annotations__}))
                elif op_type == "apply_diff":
                    ops.append(ApplyDiff(**{k: v for k, v in op_kwargs.items() if k in ApplyDiff.__annotations__}))
                else:
                    raise ValueError(f"Unknown operation type: '{op_type}'")

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
