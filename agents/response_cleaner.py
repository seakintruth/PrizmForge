# agents/response_cleaner.py

import json
import re


def extract_json_aggressively(response: str, agent_name: str) -> tuple[str | None, str]:
    """
    Aggressively extract JSON from LLM response

    Returns:
        (cleaned_json, error_reason)
    """

    if not response or not response.strip():
        return None, "Empty response"

    original_length = len(response)

    # Strategy 1: Remove markdown fences
    if "```json" in response:
        match = re.search(r"```json\s*\n(.*?)```", response, re.DOTALL | re.IGNORECASE)
        if match:
            response = match.group(1)
    elif "```" in response:
        match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
        if match:
            response = match.group(1)

    # Strategy 2: Find first { to last }
    if "{" in response and "}" in response:
        start = response.find("{")
        end = response.rfind("}")

        if end > start:
            response = response[start : end + 1]

    # Strategy 3: Remove conversational prefixes/suffixes
    response = response.strip()

    # Remove common prefixes
    prefixes_to_strip = [
        "Here is the JSON:",
        "Here's the JSON:",
        "Sure, here is",
        "Certainly,",
        "```json",
        "```",
    ]

    for prefix in prefixes_to_strip:
        if response.lower().startswith(prefix.lower()):
            response = response[len(prefix) :].strip()

    # Strategy 4: Validate it's actually JSON
    if not response.startswith("{"):
        # Last resort: find first {
        if "{" in response:
            response = response[response.find("{") :]
        else:
            return None, "No opening brace found"

    if not response.endswith("}"):
        # Last resort: find last }
        if "}" in response:
            response = response[: response.rfind("}") + 1]
        else:
            return None, "No closing brace found"

    # Strategy 5: Attempt to parse
    try:
        json.loads(response)
        print(f"    ✅ {agent_name}: Extracted valid JSON ({original_length} → {len(response)} chars)")
        return response, None
    except json.JSONDecodeError as e:
        return None, f"JSON parse failed: {e.msg} at position {e.pos}"


def clean_llm_response(response: str, agent_name: str) -> str | None:
    """
    Clean LLM response - delegates to aggressive extractor

    Returns cleaned JSON string or None if failed
    """
    cleaned, error = extract_json_aggressively(response, agent_name)

    if cleaned:
        return cleaned

    print(f"    ❌ {agent_name}: {error}")
    print(f"       First 200 chars: {response[:200]}")
    print(f"       Last 200 chars: {response[-200:]}")

    return None
