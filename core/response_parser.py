"""LLM response parsing facade over the canonical JSON parser types."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from core.json_parser import ParseResult, ParseStatus

logger = logging.getLogger(__name__)


class ResponseParser:
    """Strategy-based extraction of JSON from free-form LLM responses."""

    def __init__(self, expected_format: str = "json"):
        self.expected_format = expected_format
        self.strategies = [
            self._extract_markdown_json,
            self._extract_code_block,
            self._extract_raw_json,
        ]

    def parse(self, response: str) -> ParseResult:
        if not response or not response.strip():
            return ParseResult(
                status=ParseStatus.EMPTY,
                data=None,
                error="Empty response",
                raw_json=None,
                confidence=0.0,
            )

        last_error: str | None = None
        for strategy in self.strategies:
            try:
                extracted = strategy(response)
                if not extracted:
                    continue
                result = self._validate_and_parse(extracted)
                if result.success:
                    return result
                last_error = result.error
            except Exception as e:
                last_error = str(e)
                logger.debug("Strategy %s failed: %s", strategy.__name__, e)
                continue

        return ParseResult(
            status=ParseStatus.MALFORMED,
            data=None,
            error=last_error or "All strategies failed",
            raw_json=(response[:500] if response else None),
            confidence=0.0,
        )

    def _extract_markdown_json(self, response: str) -> str | None:
        """Extract JSON inside ```json ... ``` fences."""
        match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_code_block(self, response: str) -> str | None:
        """Extract content inside generic ``` ... ``` fences when it looks like JSON."""
        match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if not match:
            return None
        content = match.group(1).strip()
        # Drop an optional language tag on the first line. Only treat the first
        # line as a tag when it looks like an identifier AND the rest of the
        # block still begins a JSON structure — this keeps python/json5/jsonc/
        # c++/uppercase-JSON fences from being mis-read as code blocks, while a
        # `python`-tagged block whose body is not JSON is rejected as not-JSON.
        first_line = content.split("\n", 1)[0].strip()
        if first_line != content:
            body = content[len(first_line) :].lstrip("\n")
            if re.fullmatch(r"[A-Za-z0-9_+.#\-]+", first_line) and body[:1] in "{[":
                content = body.strip()
        if content.startswith("{") or content.startswith("["):
            return content
        return None

    def _extract_raw_json(self, response: str) -> str | None:
        """Best-effort brace/bracket slice from free text."""
        if not response:
            return None
        text = response.strip()
        start_brace = text.find("{")
        end_brace = text.rfind("}")
        start_bracket = text.find("[")
        end_bracket = text.rfind("]")

        candidates: list[tuple[int, str]] = []
        if start_brace != -1 and end_brace > start_brace:
            candidates.append((start_brace, text[start_brace : end_brace + 1]))
        if start_bracket != -1 and end_bracket > start_bracket:
            candidates.append((start_bracket, text[start_bracket : end_bracket + 1]))

        if not candidates:
            return None

        # Prefer the earliest starting structure
        candidates.sort(key=lambda c: c[0])
        return candidates[0][1]

    def _validate_and_parse(self, extracted: str) -> ParseResult:
        try:
            data: Any = json.loads(extracted)
            # Non-object payloads (strings, numbers, arrays) are normalized to a
            # dict under a "_value" key so all callers receive a mapping; this
            # contract is relied on by tests and downstream consumers.
            return ParseResult(
                status=ParseStatus.SUCCESS,
                data=data if isinstance(data, dict) else {"_value": data},
                error=None,
                raw_json=extracted,
                confidence=1.0,
            )
        except json.JSONDecodeError as e:
            return ParseResult(
                status=ParseStatus.MALFORMED,
                data=None,
                error=f"JSON decode error: {e.msg} at position {e.pos}",
                raw_json=extracted,
                confidence=0.0,
            )
