"""
Priority edit-path fuzz tables: path token sanitization + FILES_NEEDED extraction.

Locks regressions from unattended self-edit runs where markdown-decorated
paths (e.g. ``** `workflow/foo.py` ``) were registered as create targets.
"""

from __future__ import annotations

import pytest

from workflow.path_targets import (
    extract_files_needed_from_text,
    is_valid_edit_target_path,
    sanitize_path_token,
)

# ---------------------------------------------------------------------------
# sanitize_path_token
# ---------------------------------------------------------------------------

SANITIZE_CASES = [
    # (label, raw, expected)
    ("plain", "workflow/proposal_builder.py", "workflow/proposal_builder.py"),
    ("backticks", "`workflow/proposal_builder.py`", "workflow/proposal_builder.py"),
    ("bold_ticks", "** `workflow/proposal_builder.py`", "workflow/proposal_builder.py"),
    ("bold_wrap", "**workflow/proposal_builder.py**", "workflow/proposal_builder.py"),
    ("quotes", '"core/db.py"', "core/db.py"),
    ("trailing_comma_style", "core/db.py.", "core/db.py"),
    ("backslash", "workflow\\task_runner.py", "workflow/task_runner.py"),
    ("none_token", "NONE", None),
    ("na_token", "N/A", None),
    ("empty", "", None),
    ("whitespace", "   ", None),
    ("traversal", "../../etc/passwd", None),
    ("traversal_nested", "src/../../outside.py", None),
    ("star_only", "****", None),
    ("markdown_bold_ticks_combo", "** `database.py`", "database.py"),
]


class TestSanitizePathToken:
    @pytest.mark.parametrize("label,raw,expected", SANITIZE_CASES, ids=[c[0] for c in SANITIZE_CASES])
    def test_sanitize_cases(self, label, raw, expected):
        assert sanitize_path_token(raw) == expected, label


# ---------------------------------------------------------------------------
# extract_files_needed_from_text
# ---------------------------------------------------------------------------

EXTRACT_CASES = [
    (
        "clean_files_needed",
        "FILES_NEEDED: workflow/proposal_builder.py, core/db.py\nPLAN: fix hashes",
        ["workflow/proposal_builder.py", "core/db.py"],
    ),
    (
        "markdown_files_needed",
        "FILES_NEEDED: ** `workflow/proposal_builder.py`, `database.py`\n\nPLAN: invent module",
        ["workflow/proposal_builder.py", "database.py"],
    ),
    (
        "none_files_needed",
        "FILES_NEEDED: NONE\nPLAN: nothing",
        [],
    ),
    (
        "prose_fallback",
        "I need to examine `workflow/task_runner.py` and utils/pre_commit.sh next.",
        ["workflow/task_runner.py", "utils/pre_commit.sh"],
    ),
    (
        "prose_with_bold",
        "Update ** `file_editing/edit_payload.py` ** for create_file validation.",
        ["file_editing/edit_payload.py"],
    ),
    (
        "empty",
        "",
        [],
    ),
    (
        "dedupe",
        "FILES_NEEDED: a.py, a.py, b.py",
        ["a.py", "b.py"],
    ),
]


class TestExtractFilesNeeded:
    @pytest.mark.parametrize(
        "label,text,expected",
        EXTRACT_CASES,
        ids=[c[0] for c in EXTRACT_CASES],
    )
    def test_extract_cases(self, label, text, expected):
        assert extract_files_needed_from_text(text) == expected, label


class TestIsValidEditTargetPath:
    def test_accepts_clean_relative(self):
        assert is_valid_edit_target_path("workflow/proposal_builder.py") is True

    def test_rejects_traversal(self):
        assert is_valid_edit_target_path("../secret.py") is False

    def test_rejects_none(self):
        assert is_valid_edit_target_path(None) is False

    def test_accepts_after_markdown_only_if_sanitizable(self):
        # Raw markdown is not "already valid"; sanitize first for targets
        assert sanitize_path_token("** `core/db.py`") == "core/db.py"
        assert is_valid_edit_target_path("core/db.py") is True


class TestCreateFilePathValidation:
    """EditPayload create_file must reject decorated / traversal paths."""

    def test_create_file_clean_path_ok(self):
        from file_editing.edit_payload import CreateFile, EditPayload

        payload = EditPayload.model_validate(
            {
                "target_file_path": "pkg/new_mod.py",
                "summary": "add helper module",
                "rationale": "introduce small utility for path checks",
                "operations": [
                    {
                        "type": "create_file",
                        "target_file_path": "pkg/new_mod.py",
                        "initial_content": ["x = 1"],
                    }
                ],
            }
        )
        assert payload.operations[0].type == "create_file"
        assert payload.operations[0].target_file_path == "pkg/new_mod.py"

    def test_create_file_markdown_path_rejected(self):
        from file_editing.edit_payload import EditPayload

        with pytest.raises(ValueError, match="target_file_path"):
            EditPayload.model_validate(
                {
                    "target_file_path": "** `database.py`",
                    "summary": "bad create path",
                    "rationale": "must reject markdown decorated paths",
                    "operations": [
                        {
                            "type": "create_file",
                            "target_file_path": "** `database.py`",
                            "initial_content": ["pass"],
                        }
                    ],
                }
            )

    def test_create_file_traversal_rejected(self):
        from file_editing.edit_payload import CreateFile

        with pytest.raises(ValueError, match="target_file_path"):
            CreateFile(target_file_path="../../etc/passwd", initial_content=["x"])

    def test_top_level_target_markdown_rejected(self):
        from file_editing.edit_payload import EditPayload

        with pytest.raises(ValueError, match="target_file_path"):
            EditPayload.model_validate(
                {
                    "target_file_path": "`core/db.py`",
                    "summary": "edit existing",
                    "rationale": "path must be clean relative path",
                    "operations": [
                        {
                            "type": "find_replace",
                            "find": "a",
                            "replace": "b",
                        }
                    ],
                }
            )
