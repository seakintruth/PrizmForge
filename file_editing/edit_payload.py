# =============================================================================
# PrizmForge/file_editing/edit_payload.py
# Version: 1.3 - Improved ReplaceBlock with range support
# =============================================================================

from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Union

class BaseOperation(BaseModel):
    type: str
    rationale: str = Field(..., min_length=10, max_length=500)

class ReplaceBlock(BaseOperation):
    type: Literal["replace_block"]
    start_line_guid: str
    end_line_guid: Optional[str] = None   # If None, only replace the start line
    new_content: List[str]

class InsertAfter(BaseOperation):
    type: Literal["insert_after"]
    after_guid: Optional[str] = None
    new_content: List[str]

class DeleteLines(BaseOperation):
    type: Literal["delete_lines"]
    start_line_guid: str
    end_line_guid: Optional[str] = None   # If None, delete only the start line

class UpdateDocumentation(BaseOperation):
    type: Literal["update_documentation"]
    new_content: str

class CreateFile(BaseOperation):
    type: Literal["create_file"]
    target_file_path: str
    initial_content: List[str] = []

Operation = Union[ReplaceBlock, InsertAfter, DeleteLines, UpdateDocumentation, CreateFile]

class EditPayload(BaseModel):
    model_config = {"extra": "forbid"}
    target_file_path: str
    summary: str = Field(..., min_length=5)
    operations: List[Operation]
    rationale: str = Field(..., min_length=10)