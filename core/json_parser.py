"""
Centralized JSON parsing with edge case handling
Handles: markdown wrapping, truncation, malformed responses
"""

import json
import re
from typing import Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum


class ParseStatus(Enum):
    """JSON parse result status"""
    SUCCESS = "success"
    TRUNCATED = "truncated"
    MALFORMED = "malformed"
    EMPTY = "empty"
    WRAPPED_TEXT = "wrapped_text"


@dataclass
class ParseResult:
    """Result of JSON parsing attempt"""
    status: ParseStatus
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    raw_json: Optional[str]
    confidence: float  # 0.0 to 1.0
    
    @property
    def success(self) -> bool:
        return self.status == ParseStatus.SUCCESS
    
    @property
    def can_resume(self) -> bool:
        """Check if truncation is resumable"""
        return self.status == ParseStatus.TRUNCATED


class JSONParser:
    """
    Robust JSON parser for LLM responses
    
    Features:
    - Extracts JSON from markdown blocks
    - Handles partial/truncated JSON
    - Detects common malformations
    - Provides confidence scores
    - Suggests resume strategies
    """
    
    def __init__(self):
        self.extraction_strategies = [
            self._extract_markdown_json,
            self._extract_markdown_any,
            self._extract_brace_bounded,
            self._extract_first_json_object,
            self._extract_raw
        ]
    
    def parse(
        self, 
        response: str, 
        expected_keys: Optional[list] = None,
        strict: bool = False
    ) -> ParseResult:
        """
        Parse JSON from LLM response with multiple strategies
        
        Args:
            response: Raw LLM response text
            expected_keys: Optional list of required keys for validation
            strict: If True, fail on missing expected_keys
        
        Returns:
            ParseResult with status, data, and metadata
        """
        
        if not response or not response.strip():
            return ParseResult(
                status=ParseStatus.EMPTY,
                data=None,
                error="Empty response",
                raw_json=None,
                confidence=0.0
            )
        
        # Try extraction strategies in order
        for strategy in self.extraction_strategies:
            json_str = strategy(response)
            
            if not json_str:
                continue
            
            # Attempt to parse
            result = self._try_parse(json_str, expected_keys, strict)
            
            if result.success:
                return result
            
            # Check if truncated (resumable)
            if self._looks_truncated(json_str):
                return ParseResult(
                    status=ParseStatus.TRUNCATED,
                    data=result.data,  # Partial data if any
                    error=f"JSON appears truncated: {result.error}",
                    raw_json=json_str,
                    confidence=0.3
                )
        
        # All strategies failed
        return ParseResult(
            status=ParseStatus.MALFORMED,
            data=None,
            error="Could not extract valid JSON from response",
            raw_json=response[:500],
            confidence=0.0
        )
    
    def _extract_markdown_json(self, response: str) -> Optional[str]:
        """Extract from ```json block"""
        match = re.search(r'```json\s*\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else None
    
    def _extract_markdown_any(self, response: str) -> Optional[str]:
        """Extract from any ``` block"""
        match = re.search(r'```\s*\n(.*?)```', response, re.DOTALL)
        if match:
            content = match.group(1).strip()
            # Only return if it looks like JSON
            if content.startswith('{') or content.startswith('['):
                return content
        return None
    
    def _extract_brace_bounded(self, response: str) -> Optional[str]:
        """Extract from first { to last }"""
        if '{' not in response or '}' not in response:
            return None
        
        start = response.find('{')
        end = response.rfind('}') + 1
        
        if start < end:
            return response[start:end]
        
        return None
    
    def _extract_first_json_object(self, response: str) -> Optional[str]:
        """Extract first complete JSON object using brace matching"""
        if '{' not in response:
            return None
        
        start = response.find('{')
        depth = 0
        in_string = False
        escape = False
        
        for i in range(start, len(response)):
            char = response[i]
            
            # Handle string escaping
            if escape:
                escape = False
                continue
            
            if char == '\\':
                escape = True
                continue
            
            # Track string boundaries
            if char == '"':
                in_string = not in_string
                continue
            
            # Only count braces outside strings
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    
                    # Found complete object
                    if depth == 0:
                        return response[start:i+1]
        
        # Incomplete object found
        return response[start:]
    
    def _extract_raw(self, response: str) -> Optional[str]:
        """Try response as-is (last resort)"""
        stripped = response.strip()
        
        # Remove common prefixes
        prefixes = ['json', 'JSON', 'Here is the JSON:', 'Response:']
        for prefix in prefixes:
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix):].strip()
        
        # Remove backticks
        stripped = stripped.strip('`').strip()
        
        if stripped.startswith('{') or stripped.startswith('['):
            return stripped
        
        return None
    
    def _try_parse(
        self, 
        json_str: str, 
        expected_keys: Optional[list],
        strict: bool
    ) -> ParseResult:
        """Attempt to parse JSON string"""
        try:
            data = json.loads(json_str)
            
            # Validate expected keys
            if expected_keys:
                missing = [k for k in expected_keys if k not in data]
                
                if missing:
                    if strict:
                        return ParseResult(
                            status=ParseStatus.MALFORMED,
                            data=data,
                            error=f"Missing required keys: {missing}",
                            raw_json=json_str,
                            confidence=0.5
                        )
                    else:
                        # Partial success
                        confidence = 1.0 - (len(missing) / len(expected_keys))
                        return ParseResult(
                            status=ParseStatus.SUCCESS,
                            data=data,
                            error=f"Warning: Missing keys: {missing}",
                            raw_json=json_str,
                            confidence=confidence
                        )
            
            # Full success
            return ParseResult(
                status=ParseStatus.SUCCESS,
                data=data,
                error=None,
                raw_json=json_str,
                confidence=1.0
            )
            
        except json.JSONDecodeError as e:
            return ParseResult(
                status=ParseStatus.MALFORMED,
                data=None,
                error=f"JSON decode error: {e.msg} at position {e.pos}",
                raw_json=json_str,
                confidence=0.0
            )
    
    def _looks_truncated(self, json_str: str) -> bool:
        """Heuristic: does JSON look truncated?"""
        if not json_str:
            return False
        
        # Check for unclosed structures
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        if open_braces > close_braces or open_brackets > close_brackets:
            return True
        
        # Check if ends mid-value
        stripped = json_str.rstrip()
        if stripped and stripped[-1] not in ['}', ']', '"', 'e', '0']:  # Valid endings
            # Ends with comma or incomplete value
            if stripped[-1] in [',', ':']:
                return True
        
        # Check for incomplete string
        quote_count = json_str.count('"') - json_str.count('\\"')
        if quote_count % 2 != 0:
            return True
        
        return False
    
    def build_resume_prompt(self, partial_response: str, original_prompt: str) -> str:
        """
        Build a prompt to resume truncated JSON generation
        
        Returns:
            Continuation prompt to send to LLM
        """
        
        # Find last complete key-value
        last_comma = partial_response.rfind(',')
        last_brace = partial_response.rfind('}')
        
        cutoff_point = max(last_comma, last_brace)
        
        if cutoff_point > 0:
            context = partial_response[max(0, cutoff_point-100):cutoff_point+1]
        else:
            context = partial_response[-100:]
        
        return f"""Your previous response was truncated. Please continue from where you left off.

Original request: {original_prompt[:200]}

Your response so far (last part):
```
...{context}
```

Please continue the JSON object from this point. Start directly with the continuation (no need to repeat what you already wrote).
If the JSON was complete, please respond with: {{"status": "complete"}}
"""


# Global singleton
_json_parser = None

def get_json_parser() -> JSONParser:
    """Get global JSON parser instance"""
    global _json_parser
    if _json_parser is None:
        _json_parser = JSONParser()
    return _json_parser

def parse_json_response(
    response: str,
    expected_keys: Optional[list] = None,
    strict: bool = False,
    agent_name: str = "unknown",
    auto_resume: Callable = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function for parsing JSON responses
    
    Args:
        response: Raw LLM response
        expected_keys: Required keys to validate
        strict: Fail if keys missing
        agent_name: For logging
        auto_resume: Optional callback to request continuation
                    Signature: (prompt: str) -> str
    
    Returns:
        Parsed dict or None on failure
    """
    parser = get_json_parser()
    result = parser.parse(response, expected_keys, strict)
    
    if result.success:
        if result.error and strict:  # ✅ Only show warnings if strict mode
            print(f"    ⚠️  {agent_name}: {result.error}")
        return result.data
    
    # Handle truncation with auto-resume
    if result.can_resume and auto_resume:
        print(f"    🔄 {agent_name}: Response truncated, requesting continuation...")
        
        resume_prompt = parser.build_resume_prompt(result.raw_json, "")
        continuation = auto_resume(resume_prompt)
        
        if continuation:
            # Try to merge
            combined = result.raw_json + continuation
            retry_result = parser.parse(combined, expected_keys, strict)
            
            if retry_result.success:
                print(f"    ✅ {agent_name}: Successfully resumed truncated response")
                return retry_result.data
    
    # Failed
    print(f"    ❌ {agent_name}: JSON parse failed - {result.error}")
    print(f"       Status: {result.status.value}, Confidence: {result.confidence:.1%}")
    if result.raw_json:
        print(f"       Raw (first 200 chars): {result.raw_json[:200]}")
    
    return None