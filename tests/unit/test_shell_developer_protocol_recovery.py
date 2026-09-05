"""Phase 0 regression fixtures for the shell developer protocol.

Defines the six canonical reply shapes that must be handled predictably across
the session loop, the trajectory classifier, and the observability layer:

1. prose_only                - a reply with no command block and no finish.
2. unterminated_bash_fence   - an opening ```bash fence never closed.
3. valid_closed_bash_fence   - a properly closed ```bash``` command block.
4. finish_token_inside_block - the finish token buried inside a command block.
5. valid_finish_plus_summary - the canonical FINISH_EDIT_SESSION + summary.
6. missing_file_claim_before_command - prose claiming a file is absent, then a
                                       command that contradicts (safety case).

These fixtures are shared by Phases 1-3 via ``workflow.shell_protocol``.
"""

from __future__ import annotations

import pytest

from workflow import shell_protocol as sp

PROSE_ONLY = "I inspected the file and it looks fine. No change seems necessary."
UNTERMINATED_BASH_FENCE = "```bash\nls -la\n"
VALID_CLOSED_BASH_FENCE = "```bash\npwd && ls -la\n```"
FINISH_TOKEN_INSIDE_BLOCK = "```bash\nFINISH_EDIT_SESSION\n```"
VALID_FINISH_PLUS_SUMMARY = "FINISH_EDIT_SESSION\nSummary: no change"
MISSING_FILE_CLAIM_BEFORE_COMMAND = "The file does not exist yet.\n```bash\nmkdir -p path\n```"

ALL_FIXTURES = [
    PROSE_ONLY,
    UNTERMINATED_BASH_FENCE,
    VALID_CLOSED_BASH_FENCE,
    FINISH_TOKEN_INSIDE_BLOCK,
    VALID_FINISH_PLUS_SUMMARY,
    MISSING_FILE_CLAIM_BEFORE_COMMAND,
]


# ---------------------------------------------------------------------------
# Classification of each fixture (Phase 3.4 rules)
# ---------------------------------------------------------------------------
def test_prose_only_classified_as_prose():
    assert sp.classify_shell_reply(PROSE_ONLY) == sp.PROSE_OR_UNSUPPORTED_FORMAT


def test_unterminated_fence_classified_as_unterminated():
    assert sp.classify_shell_reply(UNTERMINATED_BASH_FENCE) == sp.UNTERMINATED_BASH_BLOCK


def test_valid_closed_fence_classified_as_valid_block():
    assert sp.classify_shell_reply(VALID_CLOSED_BASH_FENCE) == sp.VALID_BASH_BLOCK


def test_finish_inside_block_is_a_block_not_a_finish():
    assert sp.classify_shell_reply(FINISH_TOKEN_INSIDE_BLOCK) == sp.VALID_BASH_BLOCK


def test_valid_finish_classified_as_finish_session():
    assert sp.classify_shell_reply(VALID_FINISH_PLUS_SUMMARY) == sp.VALID_FINISH_SESSION


def test_missing_file_claim_is_valid_block():
    assert sp.classify_shell_reply(MISSING_FILE_CLAIM_BEFORE_COMMAND) == sp.VALID_BASH_BLOCK


# ---------------------------------------------------------------------------
# Normalization (Phase 1.3)
# ---------------------------------------------------------------------------
def test_normalize_repairs_unterminated_fence():
    normalized = sp.normalize_shell_reply(UNTERMINATED_BASH_FENCE)
    assert normalized == "```bash\nls -la\n```"
    assert sp.is_valid_bash_block(normalized)


def test_normalize_leaves_valid_block_untouched():
    assert sp.normalize_shell_reply(VALID_CLOSED_BASH_FENCE) == VALID_CLOSED_BASH_FENCE


def test_normalize_leaves_prose_untouched():
    assert sp.normalize_shell_reply(PROSE_ONLY) == PROSE_ONLY


def test_normalize_does_not_repair_missing_file_claim_multiline_prose():
    # Prose mixed with a closed command is not an "exactly one unterminated fence".
    assert sp.normalize_shell_reply(MISSING_FILE_CLAIM_BEFORE_COMMAND) == MISSING_FILE_CLAIM_BEFORE_COMMAND


def test_normalize_does_not_repair_empty_command():
    reply = "```bash\n\n"
    assert sp.normalize_shell_reply(reply) == reply


def test_normalize_does_not_repair_finish_inside_block():
    assert sp.normalize_shell_reply(FINISH_TOKEN_INSIDE_BLOCK) == FINISH_TOKEN_INSIDE_BLOCK


# ---------------------------------------------------------------------------
# Command extraction across fixtures
# ---------------------------------------------------------------------------
def test_extract_command_from_valid_block():
    assert sp.extract_bash_command(VALID_CLOSED_BASH_FENCE) == "pwd && ls -la"


def test_extract_command_from_unterminated_fence_recovered():
    assert sp.extract_bash_command(UNTERMINATED_BASH_FENCE) == "ls -la"


def test_extract_command_none_from_prose():
    assert sp.extract_bash_command(PROSE_ONLY) is None


def test_extract_command_none_from_finish():
    assert sp.extract_bash_command(VALID_FINISH_PLUS_SUMMARY) is None


def test_extract_command_ignores_finish_token_in_block():
    # A block whose only content is the finish token carries no command.
    assert sp.extract_bash_command(FINISH_TOKEN_INSIDE_BLOCK) is None


# ---------------------------------------------------------------------------
# Finish extraction across fixtures
# ---------------------------------------------------------------------------
def test_extract_finish_from_valid_summary():
    assert sp.extract_finish(VALID_FINISH_PLUS_SUMMARY) == "Summary: no change"


def test_extract_finish_absent_from_prose():
    assert sp.extract_finish(PROSE_ONLY) is None


def test_extract_finish_absent_from_block():
    assert sp.extract_finish(FINISH_TOKEN_INSIDE_BLOCK) is None


# ---------------------------------------------------------------------------
# Structured diagnostics (Phase 1.5)
# ---------------------------------------------------------------------------
def test_diagnose_prose_reason():
    assert sp.diagnose_shell_reply(PROSE_ONLY)["reason"] == "prose_or_unsupported_format"


def test_diagnose_unterminated_reason():
    assert sp.diagnose_shell_reply(UNTERMINATED_BASH_FENCE)["reason"] == "unterminated_bash_fence"


def test_diagnose_includes_excerpt_and_expected():
    diag = sp.diagnose_shell_reply(PROSE_ONLY)
    assert diag["response_excerpt"] == PROSE_ONLY[:240]
    assert diag["expected"] == "closed_bash_block_or_finish_token"


# ---------------------------------------------------------------------------
# Consistency: every fixture classifies without raising and round-trips
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_all_fixtures_classify_without_error(fixture):
    result = sp.classify_shell_reply(fixture)
    assert result in {
        sp.VALID_BASH_BLOCK,
        sp.UNTERMINATED_BASH_BLOCK,
        sp.VALID_FINISH_SESSION,
        sp.PROSE_OR_UNSUPPORTED_FORMAT,
    }


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_all_fixtures_normalize_orm_diagnose_without_error(fixture):
    sp.normalize_shell_reply(fixture)
    sp.diagnose_shell_reply(fixture)
