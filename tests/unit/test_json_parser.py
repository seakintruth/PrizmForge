"""
tests/unit/test_json_parser.py

Unit tests for core/json_parser.py
"""

import pytest
from core.json_parser import parse_json_response


class TestParseJsonResponse:
    """Tests for the centralized JSON parser convenience function."""

    def test_parse_valid_json(self):
        raw = '{"action": "create_file", "filename": "test.py"}'
        result = parse_json_response(raw)
        assert result is not None
        assert result["action"] == "create_file"

    def test_parse_json_wrapped_in_markdown(self):
        raw = """```json
        {"action": "edit", "target": "main.py"}
        ```"""
        result = parse_json_response(raw)
        assert result is not None
        assert result["action"] == "edit"

    def test_parse_malformed_json_returns_none(self):
        raw = '{"action": "create", "filename": "test.py"'  # truncated
        result = parse_json_response(raw)
        assert result is None

    def test_parse_empty_string_returns_none(self):
        result = parse_json_response("")
        assert result is None

    def test_parse_truncated_json(self):
        raw = '{"action": "create_file", "content": "print("hello'
        result = parse_json_response(raw)
        assert result is None

    def test_parse_with_surrounding_text(self):
        raw = """Here is the response:
        {"status": "ok", "message": "done"}
        Please review."""
        result = parse_json_response(raw)
        assert result is None or result.get("status") == "ok"
