"""Binary rejection — blocked_extensions from config; no exception list."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_rejects_msi_ole_magic():
    from core.content_safety import validate_source_content

    payload = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 200
    r = validate_source_content(payload.decode("latin-1"), file_path="setup.py")
    assert r["ok"] is False


def test_normalize_ext_defaults():
    from core.content_safety import _normalize_ext

    assert _normalize_ext("exe") == ".exe"  # dot-less lowercase
    assert _normalize_ext(".EXE") == ".exe"  # already dotted, case-folded
    assert _normalize_ext("..exe") == "..exe"  # preserved verbatim past the dot
    assert _normalize_ext("") == ""  # empty stays empty
    assert _normalize_ext("  .msi  ") == ".msi"  # whitespace trimmed


def test_rejects_pe_mz_header():
    from core.content_safety import validate_source_content

    pe = "MZ" + ("\x00" * 100) + "This program cannot be run in DOS mode"
    r = validate_source_content(pe, file_path="tool.py")
    assert r["ok"] is False


def test_rejects_msi_extension_even_if_text():
    from core.content_safety import validate_source_content

    r = validate_source_content("literally text", file_path="installer/Setup.msi")
    assert r["ok"] is False


def test_rejects_exe_extension():
    from core.content_safety import validate_source_content

    r = validate_source_content("print(1)", file_path="run.exe")
    assert r["ok"] is False


def test_allows_powershell_script_text():
    from core.content_safety import validate_source_content

    assert validate_source_content("Write-Host 'hello'\n", file_path="scripts/deploy.ps1")["ok"] is True


def test_allows_bat_cmd_js_text():
    from core.content_safety import validate_source_content

    assert validate_source_content("@echo off\n", file_path="run.bat")["ok"] is True
    assert validate_source_content("echo hi\n", file_path="run.cmd")["ok"] is True
    assert validate_source_content("console.log(1)\n", file_path="app.js")["ok"] is True


def test_allows_normal_source():
    from core.content_safety import validate_source_content

    assert validate_source_content("def main():\n    pass\n", file_path="app.py")["ok"] is True


def test_full_replace_rejects_binary(temp_db):
    from types import SimpleNamespace

    from file_editing.db import get_db_connection
    from file_editing.editing import apply_full_replace
    from file_editing.writer import initialize_file_lines

    initialize_file_lines("safe.py", "x = 1\n")
    with get_db_connection() as conn:
        fid = conn.execute("SELECT file_id FROM files WHERE file_path = ?", ("safe.py",)).fetchone()[0]
        op = SimpleNamespace(
            type="full_replace",
            new_content="MZ" + ("\x00" * 50) + "binary-not-source",
        )
        result = apply_full_replace(conn, fid, op)
    assert result["status"] == "error"


def test_empty_blocked_extensions_allows_msi_path_text():
    """blocked_extensions: [] disables extension blocking."""
    from core.content_safety import validate_source_content

    cfg = {
        "content_safety": {
            "disallow_binary_content": True,
            "blocked_extensions": [],
        }
    }
    r = validate_source_content("metadata text", file_path="Setup.msi", config=cfg)
    assert r["ok"] is True


def test_custom_blocked_list():
    from core.content_safety import validate_source_content

    cfg = {
        "content_safety": {
            "disallow_binary_content": True,
            "blocked_extensions": [".msi"],
        }
    }
    assert validate_source_content("text", file_path="Setup.msi", config=cfg)["ok"] is False
    # .exe not in custom list → allowed by extension (content still checked)
    assert validate_source_content("print(1)\n", file_path="run.exe", config=cfg)["ok"] is True


def test_disallow_binary_content_false():
    from core.content_safety import validate_source_content

    cfg = {
        "content_safety": {
            "disallow_binary_content": False,
            "blocked_extensions": [],
        }
    }
    pe = "MZ" + ("\x00" * 100)
    assert validate_source_content(pe, file_path="run.exe", config=cfg)["ok"] is True
