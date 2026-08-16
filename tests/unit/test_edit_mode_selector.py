"""Unit coverage for workflow.edit_mode_selector heuristics and fallback."""

from __future__ import annotations

from workflow.edit_mode_selector import (
    ALL_MODES,
    DEFAULT_FALLBACK_ORDER,
    MODE_DIFF,
    MODE_FIND_REPLACE,
    MODE_FULL_REPLACE,
    MODE_GUID,
    build_developer_edit_prompt,
    next_fallback_mode,
    select_edit_mode,
)


def test_very_small_file_prefers_full_replace():
    d = select_edit_mode(file_line_count=40, instructions="rewrite helper")
    assert d.selected_mode == MODE_FULL_REPLACE
    assert d.file_lines == 40
    assert d.fallback_chain == list(DEFAULT_FALLBACK_ORDER)


def test_rename_prefers_find_replace():
    d = select_edit_mode(file_line_count=400, instructions="rename old_name to new_name")
    assert d.selected_mode == MODE_FIND_REPLACE
    assert d.change_hint == "small"


def test_large_refactor_prefers_guid():
    d = select_edit_mode(
        file_line_count=900,
        instructions="refactor the architecture across modules",
    )
    assert d.selected_mode == MODE_GUID
    assert d.change_hint == "large"


def test_multi_file_counts_as_large():
    d = select_edit_mode(
        file_line_count=200,
        instructions="update helpers",
        files_needed=["a.py", "b.py", "c.py"],
    )
    assert d.change_hint == "large"
    assert d.selected_mode == MODE_GUID


def test_medium_on_small_file_prefers_find_replace():
    d = select_edit_mode(file_line_count=120, instructions="adjust the helper logic slightly")
    assert d.change_hint == "medium"
    assert d.selected_mode == MODE_FIND_REPLACE


def test_preferred_modes_honoured_when_no_strong_signal():
    d = select_edit_mode(
        file_line_count=500,
        instructions="do the thing",
        preferred_modes=[MODE_DIFF, MODE_GUID],
    )
    assert d.selected_mode == MODE_DIFF


def test_custom_fallback_order_filters_unknown():
    d = select_edit_mode(
        file_line_count=500,
        instructions="large redesign of the module",
        fallback_order=["bogus", MODE_FIND_REPLACE, MODE_GUID],
    )
    # Unknown modes stripped; order of remaining known modes preserved
    assert d.fallback_chain == [MODE_FIND_REPLACE, MODE_GUID]
    assert "bogus" not in d.fallback_chain


def test_empty_fallback_order_uses_default():
    d = select_edit_mode(file_line_count=500, instructions="architecture overhaul", fallback_order=[])
    assert d.fallback_chain == list(DEFAULT_FALLBACK_ORDER)


def test_next_fallback_chain_order():
    mode = MODE_GUID
    tried = []
    while mode:
        tried.append(mode)
        mode = next_fallback_mode(mode, already_tried=tried)
    assert tried == [MODE_GUID, MODE_DIFF, MODE_FIND_REPLACE, MODE_FULL_REPLACE]


def test_next_fallback_exhausted():
    assert next_fallback_mode(MODE_FULL_REPLACE, already_tried=list(ALL_MODES)) is None


def test_build_prompt_full_replace_contains_schema_keys():
    text = build_developer_edit_prompt(MODE_FULL_REPLACE, "fix it", ["# file"])
    assert "FULL REPLACE" in text
    assert "new_content" in text
    assert "START YOUR JSON OUTPUT NOW" in text


def test_build_prompt_find_replace_contains_operations():
    text = build_developer_edit_prompt(MODE_FIND_REPLACE, "rename", ["x = 1"])
    assert "FIND / REPLACE" in text
    assert "find_replace" in text


def test_build_prompt_diff_mentions_unified():
    text = build_developer_edit_prompt(MODE_DIFF, "patch", ["line"])
    assert "PLANNED DIFF" in text
    assert "unified diff" in text.lower()


def test_build_prompt_guid_default():
    text = build_developer_edit_prompt(MODE_GUID, "edit", ["guid-1 | code"])
    assert "GUID SLOC" in text or "line_guid" in text.lower()
    assert "START YOUR JSON OUTPUT NOW" in text
    assert "guid-1 | code" in text  # file content is injected
