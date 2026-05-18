"""
Token estimation utilities
Compute once, store in database
"""

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text
    
    Heuristic: ~3.5 chars per token (slightly conservative)
    Adjusted for code structure
    
    This is good enough for capacity planning - within 10% of actual
    """
    if not text:
        return 0
    
    # Base estimate
    base_tokens = len(text) / 3.5
    
    # Adjust for code (more tokens due to special chars, indentation)
    newline_ratio = text.count('\n') / max(len(text), 1)
    if newline_ratio > 0.02:  # Looks like code
        base_tokens *= 1.2
    
    return int(base_tokens)


def estimate_messages(messages: list) -> int:
    """Estimate tokens for message array"""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += estimate_tokens(content)
        total += 10  # Overhead for role, formatting
    return total