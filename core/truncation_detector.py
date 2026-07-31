"""
Truncation detection and recovery
Detects incomplete LLM responses and requests continuation
"""

import re
import json
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class TruncationType(Enum):
    """Type of truncation detected"""
    NONE = "none"
    JSON = "json"
    DIFF = "diff"
    CODE_BLOCK = "code"
    TEXT = "text"


@dataclass
class TruncationResult:
    """Result of truncation detection"""
    is_truncated: bool
    truncation_type: TruncationType
    confidence: float  # 0.0 to 1.0
    partial_content: Optional[str]
    resume_hint: Optional[str]  # What to ask LLM to continue
    
    @property
    def should_resume(self) -> bool:
        """Whether we should request continuation"""
        return self.is_truncated and self.confidence > 0.7


class TruncationDetector:
    """
    Detect truncated LLM responses
    
    Detection strategies:
    1. Structural analysis (unmatched brackets, incomplete syntax)
    2. Pattern matching (known truncation signatures)
    3. Length heuristics (suspiciously ends at round number)
    4. Content analysis (ends mid-sentence, mid-word)
    """
    
    def __init__(self, max_output_tokens: int = 16384):
        self.max_output_tokens = max_output_tokens
    
    def detect(self, response: str, expected_format: str = "auto") -> TruncationResult:
        """
        Detect if response is truncated
        
        Args:
            response: LLM response text
            expected_format: "json", "diff", "code", or "auto"
        
        Returns:
            TruncationResult with detection details
        """
        if not response:
            return TruncationResult(
                is_truncated=False,
                truncation_type=TruncationType.NONE,
                confidence=0.0,
                partial_content=None,
                resume_hint=None
            )
        
        # Auto-detect format if not specified
        if expected_format == "auto":
            expected_format = self._guess_format(response)
        
        # Try format-specific detection
        if expected_format == "json":
            return self._detect_json_truncation(response)
        elif expected_format == "diff":
            return self._detect_diff_truncation(response)
        elif expected_format == "code":
            return self._detect_code_truncation(response)
        else:
            return self._detect_generic_truncation(response)
    
    def _guess_format(self, response: str) -> str:
        """Guess expected response format"""
        if response.strip().startswith('{') or '```json' in response:
            return "json"
        elif '---' in response and '+++' in response:
            return "diff"
        elif '```' in response:
            return "code"
        else:
            return "text"
    
    def _detect_json_truncation(self, response: str) -> TruncationResult:
        """Detect truncated JSON responses"""
        # Extract JSON portion
        json_str = self._extract_json(response)
        if not json_str:
            return TruncationResult(False, TruncationType.NONE, 0.0, None, None)
        
        # Count brackets
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        # Check for unmatched brackets
        if open_braces > close_braces or open_brackets > close_brackets:
            confidence = 0.95  # Very confident
            
            # Find where truncation likely occurred
            last_comma = json_str.rfind(',')
            last_quote = json_str.rfind('"')
            cutoff = max(last_comma, last_quote)
            
            partial = json_str[:cutoff+1] if cutoff > 0 else json_str
            
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.JSON,
                confidence=confidence,
                partial_content=partial,
                resume_hint=self._build_json_resume_hint(partial)
            )
        
        # Check for incomplete strings
        # Count quotes (excluding escaped quotes)
        clean_json = re.sub(r'\\"', '', json_str)
        quote_count = clean_json.count('"')
        
        if quote_count % 2 != 0:
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.JSON,
                confidence=0.9,
                partial_content=json_str,
                resume_hint="Continue the JSON from where you left off (you were in the middle of a string value)."
            )
        
        # Check for suspicious endings
        suspicious_endings = [',', ':', '[', '"']
        if json_str.rstrip().endswith(tuple(suspicious_endings)):
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.JSON,
                confidence=0.7,
                partial_content=json_str,
                resume_hint="Continue the JSON from where you left off."
            )
        
        # Looks complete
        return TruncationResult(False, TruncationType.NONE, 0.0, None, None)
    
    def _detect_diff_truncation(self, response: str) -> TruncationResult:
        """Detect truncated unified diff"""
        # Extract diff portion
        if '```diff' in response:
            match = re.search(r'```diff\s*\n(.*?)(?:```|$)', response, re.DOTALL)
            diff_text = match.group(1) if match else response
        else:
            diff_text = response
        
        # Check for diff structure
        has_header = '---' in diff_text and '+++' in diff_text
        has_hunks = '@@' in diff_text
        
        if not has_header:
            return TruncationResult(False, TruncationType.NONE, 0.0, None, None)
        
        if not has_hunks:
            # Has header but no hunks - likely truncated
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.DIFF,
                confidence=0.85,
                partial_content=diff_text,
                resume_hint="Continue the diff from where you left off (you need to provide the @@ hunks)."
            )
        
        # Check for incomplete hunks
        lines = diff_text.split('\n')
        in_hunk = False
        last_hunk_complete = True
        
        for line in lines:
            if line.startswith('@@'):
                in_hunk = True
                last_hunk_complete = False
            elif line.startswith('---') or line.startswith('+++'):
                in_hunk = False
            elif in_hunk and line.startswith(' '):
                # Context line at end of hunk suggests completion
                last_hunk_complete = True
        
        # If last line is a change (+/-) without context, likely truncated
        last_line = lines[-1].strip() if lines else ''
        if last_line.startswith(('+', '-')) and not last_line.startswith(('+++', '---')):
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.DIFF,
                confidence=0.8,
                partial_content=diff_text,
                resume_hint="Continue the diff hunk - you need to add closing context lines."
            )
        
        # Check for unclosed markdown fence
        if '```diff' in response and response.count('```') == 1:
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.DIFF,
                confidence=0.95,
                partial_content=diff_text,
                resume_hint="Close the markdown fence with ``` and add any remaining hunks."
            )
        
        return TruncationResult(False, TruncationType.NONE, 0.0, None, None)
    
    def _detect_code_truncation(self, response: str) -> TruncationResult:
        """Detect truncated code blocks"""
        # Extract code block
        match = re.search(r'```[\w]*\s*\n(.*?)(?:```|$)', response, re.DOTALL)
        if not match:
            return TruncationResult(False, TruncationType.NONE, 0.0, None, None)
        
        code = match.group(1)
        
        # Check for unclosed markdown fence
        if response.count('```') == 1:
            confidence = 0.95
        else:
            confidence = 0.0
        
        # Python-specific checks
        if any(kw in code for kw in ['def ', 'class ', 'if ', 'for ', 'while ']):
            # Count indentation levels
            indent_stack = []
            for line in code.split('\n'):
                stripped = line.lstrip()
                if stripped and not stripped.startswith('#'):
                    indent = len(line) - len(stripped)
                    # Check if we're still inside nested block
                    if stripped.endswith(':'):
                        indent_stack.append(indent)
                    elif indent_stack and indent <= indent_stack[-1]:
                        indent_stack.pop()
            
            if indent_stack:
                # Still inside nested blocks
                confidence = max(confidence, 0.85)
        
        # Check for incomplete statements
        incomplete_patterns = [
            r'\(\s*$',  # Open paren at end
            r'\[\s*$',  # Open bracket at end
            r'=\s*$',   # Assignment without value
            r',\s*$',   # Trailing comma
        ]
        
        for pattern in incomplete_patterns:
            if re.search(pattern, code):
                confidence = max(confidence, 0.75)
                break
        
        if confidence > 0.7:
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.CODE_BLOCK,
                confidence=confidence,
                partial_content=code,
                resume_hint="Continue the code from where you left off and close with ```."
            )
        
        return TruncationResult(False, TruncationType.NONE, 0.0, None, None)
    
    def _detect_generic_truncation(self, response: str) -> TruncationResult:
        """Detect generic text truncation"""
        # Length-based heuristic
        token_estimate = len(response) / 4  # Rough estimate
        
        if token_estimate > self.max_output_tokens * 0.95:
            confidence = 0.6
        else:
            confidence = 0.0
        
        # Ends mid-sentence
        if not response.rstrip().endswith(('.', '!', '?', '```', '}', ']')):
            confidence = max(confidence, 0.5)
        
        # Ends mid-word (no space before end)
        if response and response[-1].isalnum():
            confidence = max(confidence, 0.6)
        
        if confidence > 0.5:
            return TruncationResult(
                is_truncated=True,
                truncation_type=TruncationType.TEXT,
                confidence=confidence,
                partial_content=response,
                resume_hint="Continue from where you left off."
            )
        
        return TruncationResult(False, TruncationType.NONE, 0.0, None, None)
    
    def _extract_json(self, response: str) -> Optional[str]:
        """Extract JSON portion from response"""
        if '```json' in response:
            match = re.search(r'```json\s*\n(.*?)(?:```|$)', response, re.DOTALL)
            return match.group(1) if match else None
        elif response.strip().startswith('{'):
            return response.strip()
        elif '{' in response:
            start = response.find('{')
            # Try to find end, or return rest
            end = response.rfind('}')
            if end > start:
                return response[start:end+1]
            else:
                return response[start:]
        return None
    
    def _build_json_resume_hint(self, partial_json: str) -> str:
        """Build smart resume hint for JSON"""
        # Find last complete key
        last_key_match = re.findall(r'"(\w+)":\s*(?:"[^"]*"|[\d]+|true|false|null)', partial_json)
        
        if last_key_match:
            last_key = last_key_match[-1]
            return f"Continue the JSON from where you left off. Last complete field was '{last_key}'. Start with the next field or close the object."
        else:
            return "Continue the JSON from where you left off."


# Global singleton
_truncation_detector = None

def get_truncation_detector() -> TruncationDetector:
    """Get global truncation detector"""
    global _truncation_detector
    if _truncation_detector is None:
        _truncation_detector = TruncationDetector()
    return _truncation_detector


def detect_and_resume(
    response: str,
    agent_name: str,
    original_prompt: str,
    expected_format: str = "auto",
    call_agent_fn: callable = None
) -> Tuple[str, bool]:
    """
    Convenience function: detect truncation and auto-resume
    
    Args:
        response: Original LLM response
        agent_name: Which agent to call for continuation
        original_prompt: Original prompt (for context)
        expected_format: Expected format ("json", "diff", "code", "auto")
        call_agent_fn: Function to call agent (signature: (agent, prompt, task_id) -> str)
    
    Returns:
        (final_response, was_resumed)
    """
    detector = get_truncation_detector()
    result = detector.detect(response, expected_format)
    
    if not result.should_resume:
        return response, False
    
    if not call_agent_fn:
        print(f"    ⚠️  {agent_name}: Response appears truncated but no resume function provided")
        return response, False
    
    print(f"    🔄 {agent_name}: Response truncated ({result.truncation_type.value}), requesting continuation...")
    
    # Build resume prompt
    resume_prompt = f"""Your previous response was cut off. Please continue from where you left off.

Original request: {original_prompt[:200]}...

Your response so far (last 300 chars):
...{response[-300:]}

{result.resume_hint}

IMPORTANT: Start exactly where you left off. Don't repeat what you already wrote."""
    
    # Get continuation
    continuation = call_agent_fn(agent_name, resume_prompt, "resume")
    
    if continuation:
        # Merge responses
        merged = response.rstrip() + "\n" + continuation.lstrip()
        print(f"    ✅ {agent_name}: Successfully resumed and merged response")
        return merged, True
    else:
        print(f"    ❌ {agent_name}: Resume failed")
        return response, False
    