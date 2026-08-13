import json
import logging
import re
from typing import Any

# Import the canonical ParseResult used across the repo
from core.json_parser import ParseResult

logger = logging.getLogger(__name__)


class ResponseParser:
    """Single source of truth for LLM response parsing"""

    def __init__(self, expected_format: str = "json"):
        self.expected_format = expected_format
        self.strategies = [
            self._extract_markdown_json,
            self._extract_code_block,
            self._extract_raw_json,
        ]

    def parse(self, response: str) -> ParseResult:
        for strategy in self.strategies:
            try:
                extracted = strategy(response)
                if extracted:
                    res = self._validate_and_parse(extracted)
                    if res:
                        return res
            except Exception as e:
                logger.debug(f"Strategy {strategy.__name__} failed: {e}")
                continue

        return self._make_parse_result(
            success=False,
            error="All strategies failed",
            data=None,
            raw_json=None,
            confidence=0.0,
        )

    def _extract_markdown_json(self, response: str) -> str | None:
        """Extract JSON content enclosed in markdown ```json ... ``` blocks."""
        pattern = r"```json\s*(.*?)\s*```"
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_code_block(self, response: str) -> str | None:
        """Extract content enclosed in general code blocks ``` ... ```."""
        pattern = r"```\s*(.*?)\s*```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _extract_raw_json(self, response: str) -> str | None:
        """Attempt to extract raw JSON object or array from text."""
        if not response:
            return None
        text = response.strip()
        start_brace = text.find("{")
        end_brace = text.rfind("}")
        start_bracket = text.find("[")
        end_bracket = text.rfind("]")

        if start_brace != -1 and end_brace > start_brace:
            if start_bracket != -1 and start_bracket < start_brace and end_bracket > end_brace:
                return text[start_bracket : end_bracket + 1]
            return text[start_brace : end_brace + 1]
        elif start_bracket != -1 and end_bracket > start_bracket:
            return text[start_bracket : end_bracket + 1]

        return text if text else None

    def _validate_and_parse(self, extracted: str) -> ParseResult:
        """Parse extracted JSON string and return a ParseResult."""
        try:
            data = json.loads(extracted)
            return self._make_parse_result(
                success=True,
                data=data,
                raw_json=extracted,
                confidence=1.0,
                error=None,
            )
        except Exception as e:
            logger.debug(f"Failed to parse extracted JSON: {e}")
            raise e

    def _make_parse_result(
        self,
        success: bool,
        data: Any = None,
        error: str | None = None,
        raw_json: str | None = None,
        confidence: float = 0.0,
    ) -> ParseResult:
        """Helper to safely instantiate ParseResult according to its schema."""
        kwargs = {}
        fields = getattr(ParseResult, "__dataclass_fields__", {})
        if "success" in fields:
            kwargs["success"] = success
        if "status" in fields:
            kwargs["status"] = success
        if "data" in fields:
            kwargs["data"] = data
        if "error" in fields:
            kwargs["error"] = error
        if "raw_json" in fields:
            kwargs["raw_json"] = raw_json
        if "confidence" in fields:
            kwargs["confidence"] = confidence

        if kwargs:
            return ParseResult(**kwargs)

        try:
            return ParseResult(
                status=success,
                error=error,
                data=data,
                raw_json=raw_json,
                confidence=confidence,
            )
        except Exception:
            return ParseResult(
                error=error,
                data=data,
                raw_json=raw_json,
                confidence=confidence,
            )
