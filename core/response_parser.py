from typing import Optional, Any
import logging

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
                    return self._validate_and_parse(extracted)
            except Exception as e:
                logger.debug(f"Strategy {strategy.__name__} failed: {e}")
                continue
        
        return ParseResult(status=ParseResult.__dataclass_fields__ and None, error="All strategies failed", data=None, raw_json=None, confidence=0.0)  # placeholder if needed