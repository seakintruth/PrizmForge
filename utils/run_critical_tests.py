"""
Stdlib-only critical smoke tests for hardened / Advana / minimal images.

Run:
    python -m utils.run_critical_tests

Does not require pytest. Covers path containment, mode selection,
edit validation, and MockLLM scripting.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestPathContainment(unittest.TestCase):
    def test_rejects_traversal(self):
        from core import config as config_mod
        from file_editing.writer import write_file_to_disk

        proj = Path(tempfile.mkdtemp())
        original = config_mod.get_config

        def fake():
            c = dict(original())
            c["project_directory"] = str(proj)
            return c

        config_mod.get_config = fake
        try:
            r = write_file_to_disk("../../etc/passwd", "x\n")
            self.assertEqual(r["status"], "error")
            self.assertIn("escape", r["message"].lower())
        finally:
            config_mod.get_config = original


class TestModeSelector(unittest.TestCase):
    def test_fallback_chain(self):
        from workflow.edit_mode_selector import next_fallback_mode, select_edit_mode

        d = select_edit_mode(40, "rewrite helper")
        self.assertEqual(d.selected_mode, "full_replace")

        mode = "guid"
        tried = []
        while mode:
            tried.append(mode)
            mode = next_fallback_mode(mode, already_tried=tried)
        self.assertEqual(tried, ["guid", "diff", "find_replace", "full_replace"])


class TestEditValidator(unittest.TestCase):
    def test_find_replace_and_empty(self):
        from core.edit_response_validator import EditFailureReason, validate_developer_edit_response

        ok = validate_developer_edit_response('{"target_file_path":"a.py","find":"old","replace":"new"}')
        self.assertTrue(ok.is_valid)
        self.assertEqual(ok.detected_mode, "find_replace")

        bad = validate_developer_edit_response('{"target_file_path":"a.py","summary":"x","operations":[],"rationale":"enough text here"}')
        self.assertFalse(bad.is_valid)
        self.assertEqual(bad.reason, EditFailureReason.EMPTY_OPERATIONS)


class TestMockLLM(unittest.TestCase):
    def test_scripted_call_agent(self):
        from tests.mocks.openai import MockLLM

        llm = MockLLM()
        llm.set_response("developer", '{"ok": true}')
        with llm.patch_call_agent():
            from agents.base import call_agent

            result = call_agent("developer", "hi", task_id="smoke1")
        self.assertEqual(result, '{"ok": true}')
        self.assertEqual(len(llm.calls_for("developer")), 1)


class TestEditPayloadOps(unittest.TestCase):
    def test_parse_core_ops(self):
        from file_editing.edit_payload import EditPayload

        for payload in (
            {
                "target_file_path": "a.py",
                "summary": "find replace rename",
                "rationale": "rename identifier across module",
                "operations": [
                    {
                        "type": "find_replace",
                        "find": "a",
                        "replace": "b",
                        "rationale": "rename",
                    }
                ],
            },
            {
                "target_file_path": "a.py",
                "summary": "full file replace",
                "rationale": "rewrite small file completely now",
                "operations": [
                    {
                        "type": "full_replace",
                        "new_content": "x = 1\n",
                        "rationale": "rewrite",
                    }
                ],
            },
            {
                "target_file_path": "a.py",
                "summary": "replace block line",
                "rationale": "replace a single guided line block",
                "operations": [
                    {
                        "type": "replace_block",
                        "start_line_guid": "g1",
                        "new_content": ["line"],
                        "rationale": "replace",
                    }
                ],
            },
        ):
            obj = EditPayload.model_validate(payload)
            self.assertTrue(obj.operations)
            self.assertEqual(obj.operations[0].type, payload["operations"][0]["type"])


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (
        TestPathContainment,
        TestModeSelector,
        TestEditValidator,
        TestMockLLM,
        TestEditPayloadOps,
    ):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
