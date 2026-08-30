"""
Base agent
 - functionality with multi-endpoint support
"""

import random
import re
import time

import requests

# f9 (soak recompute): background-pool agent names whose per-call transport
# failures go through the windowed coalescer (soak evidence: 275 HIGH rows from
# one rate-limited endpoint, prioritizer alone 173). Sequential agents
# (orchestrator, developer, reviewer) keep logging every failure at HIGH so the
# runner's outage guard and diagnostics stay intact.
from agents.worker_utils import classify_transport_severity
from core.config import get_agent_prompts, get_config
from core.db import get_db_path
from core.db_helpers import save_conversation
from core.endpoint_manager import EndpointConfig, EndpointStatus, get_endpoint_manager
from core.fallback_stats import log_fallback
from core.http_client import post_json
from core.json_parser import parse_json_response
from core.model_health import record_model_outcome
from core.rate_limiter import RateLimiter
from core.token_budget import TokenBudget
from file_editing.db import log_error

# Background agents that call_agent() as part of a parallel/support pool.
_BACKGROUND_TRANSPORT_AGENTS = {
    "prioritizer",
    "archivist",
    "project_reporter",
    "jr_reviewer",
    "security_reviewer",
    "jr_researcher",
    "tech_writer",
}

# Initialize
_rate_limiter = None
_token_budget = None

# Active-work tracking: HTTP latency (seconds) of the most recent call_endpoint
# invocation. Rate-limit sleeps and DB lock backoffs are excluded so iteration
# timeouts count only real work, not idle waits.
_last_call_http_latency: float = 0.0

# Agents that are allowed to return free-form text / markdown
TEXT_OUTPUT_AGENTS = {"project_reporter", "reviewer", "archivist"}


def get_rate_limiter(endpoint: EndpointConfig) -> RateLimiter:
    """Get rate limiter singleton"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(endpoint.rate_limit_per_minute)
    return _rate_limiter


def get_token_budget() -> TokenBudget:
    """Get token budget singleton"""
    global _token_budget
    if _token_budget is None:
        config = get_config()
        _token_budget = TokenBudget(get_db_path(), config["token_budget"]["max_tokens_per_4h"])
    return _token_budget


def estimate_tokens(text: str) -> int:
    """Rough token estimation"""
    return len(text) // 4


def call_endpoint(  # noqa: C901
    messages: list[dict],
    max_tokens: int | None = None,
    temperature: float | None = None,
    model: str | None = None,
    retry_count: int = 3,
    task_id: str = "unknown",
    agent_name: str = "unknown",
) -> tuple[str | None, int]:
    """Call API endpoint with automatic fallback on failure"""
    config = get_config()
    token_budget = get_token_budget()
    endpoint_mgr = get_endpoint_manager()

    # Validate and get model name (accepts "endpoint/model" or bare name)
    raw_model = model or config.get("default_model")
    choice = endpoint_mgr.normalize_model_reference(raw_model)
    if choice.endpoint_name and choice.endpoint_name in endpoint_mgr.endpoints:
        endpoint = endpoint_mgr.endpoints[choice.endpoint_name]
    else:
        endpoint = endpoint_mgr.get_endpoint_for_model(choice.model_name or raw_model)

    model_name = endpoint_mgr.validate_model(
        f"{choice.endpoint_name}/{choice.model_name}" if choice.endpoint_name and choice.model_name else (choice.model_name or raw_model)
    )

    # Per-endpoint rate limiting
    rate_limiter = get_rate_limiter(endpoint)
    rate_limiter.wait_if_needed()

    # Track HTTP latency only (rate-limit sleeps and DB lock backoffs excluded)
    global _last_call_http_latency
    _last_call_http_latency = 0.0

    # Check if endpoint is available
    if not endpoint.health.is_available():
        wait_time = endpoint.health.time_until_available()
        print(f"⚠️  {endpoint.name} unavailable ({endpoint.health.status.value})")
        print(f"   Available in {wait_time}s. Trying alternate endpoint...")

        # Try to get fallback
        fallback = endpoint_mgr.get_fallback_model(endpoint)
        if fallback:
            fallback_model, fallback_endpoint = fallback
            # Log the fallback
            log_fallback(
                original_endpoint=endpoint.name,
                fallback_endpoint=fallback_endpoint.name,
                reason=endpoint.health.status.value,
                task_id=task_id,
                agent_name=agent_name,
            )

            print(f"   → Falling back to {fallback_endpoint.name}/{fallback_model}")
            return call_endpoint(
                messages,
                max_tokens,
                temperature,
                fallback_model,
                retry_count,
                task_id,
                agent_name,
            )
        else:
            print("   ❌ No alternate endpoints available")
            return None, 0

    # Build payload for this endpoint
    payload = endpoint_mgr.build_payload(endpoint, model_name, messages, max_tokens, temperature)

    # Estimate tokens
    input_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
    estimated_output = payload["max_tokens"] // 2
    estimated_total = input_tokens + estimated_output

    if not token_budget.can_spend(estimated_total):
        print("⚠️  Token budget exceeded. Trying alternate endpoint...")
        fallback = endpoint_mgr.get_fallback_model(endpoint)
        if fallback:
            fallback_model, fallback_endpoint = fallback
            # Log the fallback
            log_fallback(
                original_endpoint=endpoint.name,
                fallback_endpoint=fallback_endpoint.name,
                reason=endpoint.health.status.value,
                task_id=task_id,
                agent_name=agent_name,
            )
            print(f"   → Falling back to {fallback_endpoint.name}/{fallback_model}")
            return call_endpoint(
                messages,
                max_tokens,
                temperature,
                fallback_model,
                retry_count,
                task_id,
                agent_name,
            )
        return None, 0

    # Get API key for this endpoint
    try:
        api_key = endpoint_mgr.get_api_key(endpoint)
    except ValueError as e:
        print(f"❌ {e}")
        endpoint.health.mark_failure(EndpointStatus.KEY_LOCKED)
        record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="key_locked")

        # Try fallback
        fallback = endpoint_mgr.get_fallback_model(endpoint)
        if fallback:
            fallback_model, fallback_endpoint = fallback
            # Log the fallback
            log_fallback(
                original_endpoint=endpoint.name,
                fallback_endpoint=fallback_endpoint.name,
                reason=endpoint.health.status.value,
                task_id=task_id,
                agent_name=agent_name,
            )

            print(f"   → Falling back to {fallback_endpoint.name}/{fallback_model}")
            return call_endpoint(
                messages,
                max_tokens,
                temperature,
                fallback_model,
                retry_count,
                task_id,
                agent_name,
            )

        return None, 0

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    proxies = config.get("proxy")

    for attempt in range(retry_count):
        _req_t0 = time.time()
        try:
            resp = post_json(
                endpoint.base_url,
                headers=headers,
                json_body=payload,
                timeout=120,
                proxies=proxies,
            )
            _last_call_http_latency += time.time() - _req_t0

            # Attempt to extract error JSON safely
            error_data = {}
            try:
                resp_json = resp.json()
                if "error" in resp_json and isinstance(resp_json["error"], dict):
                    error_data = resp_json["error"]
            except Exception as e:
                print(f"    ⚠️  Response body was not valid JSON: {e}")

            # ============= HANDLE 401 / UNAUTHORIZED (KEY LOCKED) =============
            if resp.status_code == 401 or error_data.get("type") == "unauthorized":
                unlock_url = error_data.get("unlock_url")
                error_msg = error_data.get("message", "API KEY LOCKED OR INVALID")

                # ✅ If we got an unlock URL, pause for 2 minutes to let the user click it
                if unlock_url:
                    print(f"\n{'=' * 60}")
                    print(f"🔒 {error_msg.upper()} ({endpoint.name})")
                    print(f"👉 CLICK TO UNLOCK: {unlock_url}")
                    print("⏳ Pausing for 2 minutes to allow you to unlock the API...")
                    print(f"{'=' * 60}\n")

                    time.sleep(120)  # Wait 2 minutes for user to unlock

                    # Try the request one more time after waiting
                    try:
                        resp = post_json(
                            endpoint.base_url,
                            headers=headers,
                            json_body=payload,
                            timeout=120,
                            proxies=proxies,
                        )
                        _last_call_http_latency += time.time() - _req_t0

                        retry_error_data = {}
                        try:
                            retry_json = resp.json()
                            if "error" in retry_json and isinstance(retry_json["error"], dict):
                                retry_error_data = retry_json["error"]
                        except Exception as e:
                            print(f"    ⚠️  Response body was not valid JSON during retry: {e}")

                        # Check if the retry succeeded
                        if resp.status_code == 200 and retry_error_data.get("type") != "unauthorized":
                            print(f"✅ API successfully unlocked ({endpoint.name})! Resuming...")
                            resp.raise_for_status()
                            # Skip the fallback below, continue to normal parsing
                        else:
                            raise ValueError("API still locked after wait.")

                    except Exception:
                        # Still locked/failed after waiting, let it fall through to the fallback logic below
                        print("❌ API still locked after 2 minutes.")
                else:
                    # No unlock URL provided, just print the standard error and skip the sleep
                    print(f"\n{'=' * 60}")
                    print(f"🔒 {error_msg.upper()} ({endpoint.name})")
                    print(f"{'=' * 60}\n")

                # === Fallback Logic (Executes if no unlock_url, or if retry failed) ===
                endpoint.health.mark_failure(EndpointStatus.KEY_LOCKED, cooldown_minutes=30)
                record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="unauthorized")
                fallback = endpoint_mgr.get_fallback_model(endpoint)
                if fallback:
                    fallback_model, fallback_endpoint = fallback
                    log_fallback(
                        original_endpoint=endpoint.name,
                        fallback_endpoint=fallback_endpoint.name,
                        reason=EndpointStatus.KEY_LOCKED.value,
                        task_id=task_id,
                        agent_name=agent_name,
                    )
                    print(f"→ Automatically falling back to {fallback_endpoint.name}/{fallback_model}")
                    return call_endpoint(
                        messages,
                        max_tokens,
                        temperature,
                        fallback_model,
                        retry_count,
                        task_id,
                        agent_name,
                    )
                return None, 0

            # ============= HANDLE 429 RATE LIMIT =============
            if resp.status_code == 429:
                print(f"⏳ Rate limited ({endpoint.name})...")

                # AIMD: reduce our effective capacity so concurrent consumers of a
                # shared upstream window do not keep stacking calls together.
                rate_limiter.on_rate_limited()

                try:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                except (TypeError, ValueError):
                    retry_after = 60

                # Diagnostics: surface rate-limit headers + server-side message so
                # upstream throttling is visible without digging into the network.
                _limit_headers = {
                    "retry-after",
                    "ratelimit-limit",
                    "ratelimit-remaining",
                    "ratelimit-reset",
                    "x-ratelimit-remaining",
                    "x-ratelimit-reset",
                    "x-ratelimit-limit",
                }
                rate_headers = {k: v for k, v in resp.headers.items() if k.lower() in _limit_headers}
                if rate_headers:
                    print(f"   Rate-limit headers: {rate_headers}")
                if error_data.get("message"):
                    print(f"   Server: {str(error_data['message'])[:200]}")

                if retry_after > 60:  # If wait is > 1 minute, try fallback
                    endpoint.health.mark_failure(EndpointStatus.RATE_LIMITED, cooldown_minutes=2)
                    record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="rate_limited")
                    print(f"   Rate limit cooldown too long ({retry_after}s)")

                    fallback = endpoint_mgr.get_fallback_model(endpoint)
                    if fallback:
                        fallback_model, fallback_endpoint = fallback
                        # Log the fallback
                        log_fallback(
                            original_endpoint=endpoint.name,
                            fallback_endpoint=fallback_endpoint.name,
                            reason=endpoint.health.status.value,
                            task_id=task_id,
                            agent_name=agent_name,
                        )
                        print(f"   → Falling back to {fallback_endpoint.name}/{fallback_model}")
                        return call_endpoint(
                            messages,
                            max_tokens,
                            temperature,
                            fallback_model,
                            retry_count,
                            task_id,
                            agent_name,
                        )

                # Otherwise wait (Retry-After + exponential backoff + jitter) and
                # retry. The jitter desynchronizes concurrent sleepers that share
                # the upstream window.
                backoff = 2**attempt + random.uniform(0, 5)  # noqa: S311
                sleep_for = max(retry_after, backoff)
                print(f"   Sleeping {sleep_for:.1f}s...")
                time.sleep(sleep_for)
                continue

            # ============= HANDLE 402 TOKEN EXHAUSTED =============
            if resp.status_code == 402:
                print(f"💰 Token quota exhausted ({endpoint.name})")

                # Mark endpoint as unavailable
                endpoint.health.mark_failure(EndpointStatus.TOKEN_EXHAUSTED, cooldown_minutes=15)
                record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="token_exhausted")

                # Try fallback immediately
                print(f"⚠️  {endpoint.name} marked as unavailable for 15 minutes")
                fallback = endpoint_mgr.get_fallback_model(endpoint)
                if fallback:
                    fallback_model, fallback_endpoint = fallback
                    # Log the fallback
                    log_fallback(
                        original_endpoint=endpoint.name,
                        fallback_endpoint=fallback_endpoint.name,
                        reason=endpoint.health.status.value,
                        task_id=task_id,
                        agent_name=agent_name,
                    )
                    print(f"→ Automatically falling back to {fallback_endpoint.name}/{fallback_model}")
                    return call_endpoint(
                        messages,
                        max_tokens,
                        temperature,
                        fallback_model,
                        retry_count,
                        task_id,
                        agent_name,
                    )
                else:
                    print("❌ No alternate endpoints available")
                    return None, 0

            # ============= HANDLE 5xx SERVER ERRORS =============
            if resp.status_code >= 500:
                wait_time = (2**attempt) + (time.time() % 1)
                print(f"⚠️  Server error {resp.status_code} ({endpoint.name}). Retry {attempt + 1}/{retry_count}")

                # On last retry, try fallback
                if attempt == retry_count - 1:
                    endpoint.health.mark_failure(EndpointStatus.SERVER_ERROR, cooldown_minutes=5)
                    record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="server_error")

                    fallback = endpoint_mgr.get_fallback_model(endpoint)
                    if fallback:
                        fallback_model, fallback_endpoint = fallback
                        # Log the fallback
                        log_fallback(
                            original_endpoint=endpoint.name,
                            fallback_endpoint=fallback_endpoint.name,
                            reason=endpoint.health.status.value,
                            task_id=task_id,
                            agent_name=agent_name,
                        )
                        print(f"→ Server unreachable. Falling back to {fallback_endpoint.name}/{fallback_model}")
                        return call_endpoint(
                            messages,
                            max_tokens,
                            temperature,
                            fallback_model,
                            retry_count,
                            task_id,
                            agent_name,
                        )

                time.sleep(wait_time)
                continue

            resp.raise_for_status()
            data = resp.json()

            # Extract response using endpoint-specific path
            try:
                answer = endpoint.extract_response(data)
            except (KeyError, ValueError, IndexError) as e:
                print(f"❌ Failed to parse response from {endpoint.name}: {e}")
                print(f"   Response keys: {list(data.keys())}")

                # Mark endpoint as having issues
                endpoint.health.mark_failure(EndpointStatus.UNAVAILABLE, cooldown_minutes=5)
                record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="bad_payload")

                # Try fallback
                fallback = endpoint_mgr.get_fallback_model(endpoint)
                if fallback:
                    fallback_model, fallback_endpoint = fallback
                    # Log the fallback
                    log_fallback(
                        original_endpoint=endpoint.name,
                        fallback_endpoint=fallback_endpoint.name,
                        reason=endpoint.health.status.value,
                        task_id=task_id,
                        agent_name=agent_name,
                    )
                    print(f"→ Falling back to {fallback_endpoint.name}/{fallback_model}")
                    return call_endpoint(
                        messages,
                        max_tokens,
                        temperature,
                        fallback_model,
                        retry_count,
                        task_id,
                        agent_name,
                    )

                return None, 0

            # ============= SUCCESS =============
            # Mark endpoint as healthy
            endpoint.health.mark_success()
            record_model_outcome(
                f"{endpoint.name}/{model_name}",
                endpoint.name,
                ok=True,
                latency_ms=int((time.time() - _req_t0) * 1000),
            )

            # AIMD: a successful call earns back a step of effective capacity.
            rate_limiter.on_success()

            # Track tokens
            output_tokens = estimate_tokens(answer)
            total_tokens = input_tokens + output_tokens
            token_budget.add_usage(total_tokens)

            return answer, total_tokens

        except requests.exceptions.Timeout:
            # ✅ Added Agent Attribution and Attempt Tracker
            print(f"  ⏱️  {agent_name.upper()} timed out calling {endpoint.name} (Attempt {attempt + 1}/{retry_count})")

            if attempt == retry_count - 1:
                endpoint.health.mark_failure(EndpointStatus.UNAVAILABLE, cooldown_minutes=5)
                record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="timeout")

                fallback = endpoint_mgr.get_fallback_model(endpoint)
                if fallback:
                    fallback_model, fallback_endpoint = fallback
                    log_fallback(
                        original_endpoint=endpoint.name,
                        fallback_endpoint=fallback_endpoint.name,
                        reason=EndpointStatus.UNAVAILABLE.value,
                        task_id=task_id,
                        agent_name=agent_name,
                    )
                    print(f"  → {agent_name} falling back to {fallback_endpoint.name}/{fallback_model}")
                    return call_endpoint(
                        messages,
                        max_tokens,
                        temperature,
                        fallback_model,
                        retry_count,
                        task_id,
                        agent_name,
                    )
                return None, 0

            # ✅ Make the retry visible
            print(f"  🔄 Retrying {agent_name} in {2**attempt}s...")
            time.sleep(2**attempt)

        except requests.exceptions.RequestException as e:
            error_str = str(e).lower()

            # Handle proxy or auth errors gracefully by pausing
            if "proxy" in error_str or "auth" in error_str or "forbidden" in error_str:
                print(f"\n{'=' * 60}")
                print(f"🔒 CONNECTION/PROXY ERROR for {agent_name.upper()} ({endpoint.name}): {e}")
                print("⏳ Pausing for 2 minutes to allow you to fix the connection...")
                print(f"{'=' * 60}\n")
                time.sleep(120)
            else:
                # ✅ Added Agent Attribution to standard request failures
                print(f"  ❌ {agent_name.upper()} request failed ({endpoint.name}) [Attempt {attempt + 1}/{retry_count}]: {e}")

            if attempt == retry_count - 1:
                endpoint.health.mark_failure(EndpointStatus.UNAVAILABLE, cooldown_minutes=5)
                record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="request_error")

                fallback = endpoint_mgr.get_fallback_model(endpoint)
                if fallback:
                    fallback_model, fallback_endpoint = fallback
                    log_fallback(
                        original_endpoint=endpoint.name,
                        fallback_endpoint=fallback_endpoint.name,
                        reason=EndpointStatus.UNAVAILABLE.value,
                        task_id=task_id,
                        agent_name=agent_name,
                    )
                    print(f"  → {agent_name} falling back to {fallback_endpoint.name}/{fallback_model}")
                    return call_endpoint(
                        messages,
                        max_tokens,
                        temperature,
                        fallback_model,
                        retry_count,
                        task_id,
                        agent_name,
                    )

                return None, 0

            print(f"  🔄 Retrying {agent_name} in {2**attempt}s...")
            time.sleep(2**attempt)

        except Exception as e:
            # ✅ Added Agent Attribution to unexpected errors
            print(f"  ❌ {agent_name.upper()} encountered unexpected error ({endpoint.name}): {e}")
            import traceback

            traceback.print_exc()

            endpoint.health.mark_failure(EndpointStatus.UNAVAILABLE, cooldown_minutes=5)
            record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="unexpected_error")

            fallback = endpoint_mgr.get_fallback_model(endpoint)
            if fallback:
                fallback_model, fallback_endpoint = fallback
                log_fallback(
                    original_endpoint=endpoint.name,
                    fallback_endpoint=fallback_endpoint.name,
                    reason=EndpointStatus.UNAVAILABLE.value,
                    task_id=task_id,
                    agent_name=agent_name,
                )
                print(f"  → {agent_name} falling back to {fallback_endpoint.name}/{fallback_model}")
                return call_endpoint(
                    messages,
                    max_tokens,
                    temperature,
                    fallback_model,
                    retry_count,
                    task_id,
                    agent_name,
                )

            return None, 0

    # All retries exhausted
    print(f"❌ All retries exhausted for {endpoint.name}")
    endpoint.health.mark_failure(EndpointStatus.UNAVAILABLE, cooldown_minutes=5)
    record_model_outcome(f"{endpoint.name}/{model_name}", endpoint.name, ok=False, kind="retries_exhausted")

    fallback = endpoint_mgr.get_fallback_model(endpoint)
    if fallback:
        fallback_model, fallback_endpoint = fallback
        # Log the fallback
        log_fallback(
            original_endpoint=endpoint.name,
            fallback_endpoint=fallback_endpoint.name,
            reason=endpoint.health.status.value,
            task_id=task_id,
            agent_name=agent_name,
        )
        print(f"→ Falling back to {fallback_endpoint.name}/{fallback_model}")
        return call_endpoint(
            messages,
            max_tokens,
            temperature,
            fallback_model,
            retry_count,
            task_id,
            agent_name,
        )

    return None, 0


def call_agent(  # noqa: C901
    agent_name: str,
    prompt: str,
    task_id: str,
    context: list[dict] | None = None,
    model_override: str | None = None,
    auto_resume: bool = True,
    max_resume_attempts: int = 1,
    _is_repair_attempt: bool = False,
) -> str | None:
    """Call agent with schema injection and controlled JSON repair."""
    from core.agent_schemas import get_schema_example
    from core.archival import archive_raw_response

    config = get_config()

    # Config/env mock LLM — no network (unattended test mode)
    try:
        from core.llm_test_mode import mock_call_agent, test_mode_enabled

        if test_mode_enabled(config):
            print(f"  🧪 test_mode: mock LLM response for {agent_name}")
            return mock_call_agent(agent_name, prompt, task_id, config)
    except Exception as e:
        print(f"  ⚠️  LLM test mode check skipped: {e}")

    endpoint_mgr = get_endpoint_manager()

    # ============= MODEL + ENDPOINT RESOLUTION =============
    # Priority: explicit model_override > resource-controller throttle override > agent prefs
    if model_override is None:
        try:
            from agents.resource_controller_worker import get_resource_controller

            rc_override = get_resource_controller().get_model_override(agent_name)
            if rc_override:
                model_override = rc_override
                print(f"  🎛️  Resource controller: using {rc_override} for {agent_name}")
        except Exception as e:
            print(f"  ⚠️  Resource controller model override check failed: {e}")

    # LLM-supplied overrides (orchestrator decision "model" field) are NOT
    # trusted blindly — models hallucinate names from prompt examples. Only
    # accept an override that actually resolves; otherwise fall through to
    # the configured agent preferences.
    if model_override and not endpoint_mgr.model_reference_exists(model_override):
        print(f"  ⚠️  Ignoring unknown model override '{model_override}' for {agent_name} (not in endpoints/models); using configured preference instead")
        model_override = None

    if model_override:
        choice = endpoint_mgr.normalize_model_reference(model_override)
    else:
        choice = endpoint_mgr.resolve_agent_model(agent_name)

    model = choice.model_name
    if choice.endpoint_name and choice.endpoint_name in endpoint_mgr.endpoints:
        endpoint = endpoint_mgr.endpoints[choice.endpoint_name]
    else:
        endpoint = endpoint_mgr.get_endpoint_for_model(model)

    # validate_model returns bare model name for API payloads
    model = endpoint_mgr.validate_model(f"{choice.endpoint_name}/{model}" if choice.endpoint_name and model else model)
    endpoint_name = endpoint.name if endpoint else "default"
    # ============================================================

    # Load agent prompts
    try:
        prompts = get_agent_prompts()
    except FileNotFoundError as e:
        print(f"❌ Error loading agent prompts: {e}")
        return None

    if agent_name not in prompts:
        print(f"❌ Unknown agent: {agent_name}")
        print(f"   Available agents: {', '.join(prompts.keys())}")
        return None

    system_prompt = prompts[agent_name]["system_prompt"]

    # Log prompt size
    full_prompt_length = len(system_prompt) + len(prompt)
    if context:
        full_prompt_length += sum(len(m.get("content", "")) for m in context[-10:])

    print(f"  🤖 Calling {agent_name} via {endpoint_name}/{model or 'default'}...")
    print(f"     Prompt: {full_prompt_length} chars, Context: {len(context) if context else 0} msgs")

    # Only inject schemas for JSON-outputting agents
    if agent_name not in TEXT_OUTPUT_AGENTS:
        schema_example = get_schema_example(agent_name)

        system_prompt += f"""

**MANDATORY OUTPUT FORMAT:**

Your ENTIRE response must be valid JSON matching this structure EXACTLY:

{schema_example}

**CRITICAL RULES:**
- First character of your response: {{
- Last character of your response: }}
- No text before the {{
- No text after the }}
- No markdown fences (```json)
- Use standard JSON quotes (\")

If you cannot analyze the file, return:
{{"error": "Unable to analyze", "summary": "Analysis failed"}}
    """

    messages = [{"role": "system", "content": system_prompt}]

    if context:
        messages.extend(context[-10:])

    messages.append({"role": "user", "content": prompt})

    # Track start time for performance metrics
    start_time = time.time()

    # ============= CALL ENDPOINT =============
    response, tokens = call_endpoint(messages, model=model, task_id=task_id, agent_name=agent_name)

    # ============= ARCHIVE OR LOG ERROR =============
    if response is not None:
        # Only archive successful connections
        archive_raw_response(task_id, agent_name, prompt, response, True, None)
    else:
        # Log the network/API failure to the central errors table
        try:
            if agent_name in _BACKGROUND_TRANSPORT_AGENTS:
                severity = classify_transport_severity(agent_name, "call_agent")
            else:
                severity = "HIGH"
            log_error(
                component="agents.base",
                category="call_agent",
                severity=severity,
                message=f"{agent_name} failed to return a response (API/Network error)",
                task_id=task_id,
                details={
                    "prompt_length": len(prompt),
                    "model": model,
                    "agent_name": agent_name,
                },
                agent_name=agent_name,
            )
        except Exception as e:
            print(f"  ⚠️  Failed to log error: {e}")

        print(f"  ❌ {agent_name} failed")
        return None

    # ============= UPDATE RESOURCE CONTROLLER =============
    try:
        duration = time.time() - start_time

        # Count feedback items generated (estimate from response)
        feedback_count = 0
        if response and agent_name in ["jr_reviewer", "jr_researcher", "tech_writer"]:
            feedback_count = response.count('"priority"')

        from agents.resource_controller_worker import get_resource_controller

        rc = get_resource_controller()
        rc.update_agent_performance(agent_name, tokens, duration, feedback_count)
    except Exception as e:
        print(f"  ⚠️  Resource controller performance update failed: {e}")
    # =====================================================

    # ------------------------------------------------------------------
    # CONTROLLED ONE-SHOT JSON REPAIR
    # ------------------------------------------------------------------
    # Only for strict JSON agents, only when the response is non-empty
    # but fails to parse, and only once (guarded by _is_repair_attempt).
    if not _is_repair_attempt and agent_name not in TEXT_OUTPUT_AGENTS and response and response.strip():
        probe = parse_json_response(
            response,
            strict=False,
            agent_name=agent_name,
        )
        if probe is None:
            print(f"  🔧 {agent_name}: response failed JSON parse — attempting one-shot repair")
            repair_prompt = (
                "Your previous response was not valid JSON.\n\n"
                "Convert the decision or information you already produced into a single "
                "valid JSON object. Reply with ONLY the JSON object.\n"
                "- First character must be {\n"
                "- Last character must be }\n"
                "- No markdown fences, no commentary, no headings, no explanation.\n"
            )
            repair_context = (context or []) + [{"role": "assistant", "content": response[:4000]}]
            repaired = call_agent(
                agent_name,
                repair_prompt,
                task_id,
                context=repair_context,
                model_override=model_override,
                auto_resume=False,
                max_resume_attempts=0,
                _is_repair_attempt=True,
            )
            if repaired and repaired.strip():
                # Prefer the repaired version if it now parses; otherwise keep original
                repaired_probe = parse_json_response(repaired, strict=False, agent_name=agent_name)
                if repaired_probe is not None:
                    print(f"  ✅ {agent_name}: JSON repair succeeded")
                    response = repaired
                else:
                    print(f"  ⚠️  {agent_name}: repair attempt also failed to produce valid JSON — keeping original")
            else:
                print(f"  ⚠️  {agent_name}: repair call returned empty — keeping original")

    # ✅ TRUNCATION DETECTION AND AUTO-RESUME
    if auto_resume and max_resume_attempts > 0:
        # ✅ DETERMINE EXPECTED FORMAT based on agent's output type
        expected_format = _get_agent_output_format(agent_name, system_prompt)

        from core.truncation_detector import get_truncation_detector

        detector = get_truncation_detector()
        truncation_result = detector.detect(response, expected_format)

        if truncation_result.should_resume:
            print(f"  🔄 {agent_name}: Truncated {truncation_result.truncation_type.value} detected (confidence: {truncation_result.confidence:.0%})")
            print(f"     Attempts remaining: {max_resume_attempts}")

            # Build resume prompt
            resume_prompt = f"""Your previous response was cut off. Please continue from where you left off.

Original request: {prompt[:300]}...

Your response so far (last 300 chars):
...{response[-300:]}

{truncation_result.resume_hint}

IMPORTANT: Start exactly where you left off. Don't repeat what you already wrote."""

            # Recursive call with decremented attempts
            continuation = call_agent(
                agent_name,
                resume_prompt,
                task_id,
                context,
                model_override,
                auto_resume=True,
                max_resume_attempts=max_resume_attempts - 1,
            )

            if continuation:
                # ✅ SMART MERGING based on format
                merged = _merge_responses(response, continuation, expected_format)

                # Archive merged response
                archive_raw_response(
                    task_id,
                    agent_name,
                    f"[RESUMED_{max_resume_attempts}] {prompt}",
                    merged,
                    True,
                    None,
                )

                print(f"  ✅ {agent_name} resumed and merged ({len(merged)} chars total)")
                return merged
            else:
                print(f"  ⚠️  {agent_name} resume failed, using truncated response")

    # ============= SUCCESS =============
    save_conversation(task_id, agent_name, "assistant", response[:500], raw_response=response)
    print(f"  ✅ {agent_name} responded ({tokens} tokens)")
    return response


def _get_agent_output_format(agent_name: str, system_prompt: str) -> str:
    """
    Determine expected output format for an agent

    Strategy:
    1. Check explicit format indicators in agent name
    2. Check system prompt for format hints
    3. Fall back to defaults

    Returns:
        "json", "diff", "text", or "code"
    """
    # Explicit format based on agent name
    if agent_name == "developer":
        return "diff"

    # Check system prompt for format hints
    prompt_lower = system_prompt.lower()

    if "respond with only valid json" in prompt_lower or "json only" in prompt_lower:
        return "json"

    if "respond in plain text" in prompt_lower or "respond in markdown" in prompt_lower:
        return "text"

    if "output changes as diffs" in prompt_lower or "unified diff" in prompt_lower:
        return "diff"

    # Specific known text-output agents
    text_agents = ["reviewer", "researcher", "project_reporter"]
    if agent_name in text_agents:
        return "text"

    # Default: most agents use JSON
    return "json"


def _merge_responses(original: str, continuation: str, format_type: str) -> str:
    """
    Smart merge of responses based on format type

    Args:
        original: Original (truncated) response
        continuation: Continuation response
        format_type: "json", "diff", "text", or "code"

    Returns:
        Merged response
    """
    if format_type == "json":
        return _merge_json_responses(original, continuation)
    elif format_type == "diff":
        return _merge_diff_responses(original, continuation)
    elif format_type == "text":
        return _merge_text_responses(original, continuation)
    else:
        # Generic merge (simple concatenation)
        return original.rstrip() + "\n" + continuation.lstrip()


def _merge_json_responses(original: str, continuation: str) -> str:
    """
    Smart merge of JSON responses wrapped in markdown

    Handles:
    - Original: "Here's the result:\n```json\n{\"field\": \"val\n```"
    - Continuation: "```json\nue\", \"field2\": \"val2\"}\n```\nDone!"

    Result: "Here's the result:\n```json\n{\"field\": \"value\", \"field2\": \"val2\"}\n```\nDone!"
    """

    # Extract prefix (text before JSON)
    prefix = ""
    if "```json" in original:
        prefix = original.split("```json")[0]
    elif "```" in original:
        prefix = original.split("```")[0]

    # Extract suffix (text after JSON in continuation)
    suffix = ""
    if "```" in continuation:
        parts = continuation.split("```")
        if len(parts) > 2:
            # Text after closing ```
            suffix = parts[-1].strip()
            if suffix:
                suffix = "\n" + suffix

    # Extract JSON portions (strip markdown)
    original_json = _extract_json_content(original)
    continuation_json = _extract_json_content(continuation)

    # Merge JSON portions
    # Remove trailing ``` or incomplete closing from original
    original_json = original_json.rstrip()
    if original_json.endswith("```"):
        original_json = original_json[:-3].rstrip()

    # Remove leading ``` or markdown prefix from continuation
    continuation_json = continuation_json.lstrip()

    # Merge
    merged_json = original_json + continuation_json

    # Reconstruct with markdown
    return f"{prefix}```json\n{merged_json}\n```{suffix}"


def _extract_json_content(text: str) -> str:
    """
    Extract JSON content, stripping markdown fences and surrounding text

    Handles:
    - "```json\n{...}\n```" → "{...}"
    - "Here's JSON:\n```json\n{...}" → "{...}"
    - "{...}\n```\nMore text" → "{...}"
    """
    # Strategy 1: Extract from ```json block
    if "```json" in text:
        match = re.search(r"```json\s*\n(.*?)(?:```|$)", text, re.DOTALL)
        if match:
            return match.group(1)

    # Strategy 2: Extract from generic ``` block
    if "```" in text:
        match = re.search(r"```\s*\n(.*?)(?:```|$)", text, re.DOTALL)
        if match:
            content = match.group(1)
            # Only use if it looks like JSON
            if content.strip().startswith(("{", "[")):
                return content

    # Strategy 3: Find first { to last } (or end)
    if "{" in text:
        start = text.find("{")
        end = text.rfind("}")

        if end > start:
            # Complete JSON
            return text[start : end + 1]
        else:
            # Truncated JSON (no closing brace found)
            # Return from first { to end, removing trailing ```
            json_part = text[start:]
            if "```" in json_part:
                json_part = json_part.split("```")[0]
            return json_part

    # Strategy 4: Return as-is (let caller handle)
    return text


def _merge_diff_responses(original: str, continuation: str) -> str:
    """
    Smart merge of diff responses

    Simpler than JSON - just strip markdown fences and concatenate
    """
    # Extract diff content from markdown
    original_diff = _extract_diff_content(original)
    continuation_diff = _extract_diff_content(continuation)

    # Check if we need to preserve markdown wrapper
    has_markdown = "```diff" in original or "```" in original

    if has_markdown:
        return f"```diff\n{original_diff}\n{continuation_diff}\n```"
    else:
        return f"{original_diff}\n{continuation_diff}"


def _extract_diff_content(text: str) -> str:
    """Extract diff content, stripping markdown"""
    if "```diff" in text:
        match = re.search(r"```diff\s*\n(.*?)(?:```|$)", text, re.DOTALL)
        if match:
            return match.group(1).rstrip()

    if "```" in text:
        match = re.search(r"```\s*\n(.*?)(?:```|$)", text, re.DOTALL)
        if match:
            content = match.group(1)
            # Only use if it looks like a diff
            if "---" in content or "+++" in content or content.startswith(("-", "+", " ")):
                return content.rstrip()

    # No markdown, return as-is
    return text.rstrip()


def _merge_text_responses(original: str, continuation: str) -> str:
    """
    Merge text/markdown responses

    Strategy:
    - Check if original ends mid-sentence
    - Check if continuation starts with continuation indicators
    - Merge appropriately (no space if mid-word, space if mid-sentence)
    """
    original_trimmed = original.rstrip()
    continuation_trimmed = continuation.lstrip()

    # Check if original ends mid-word (no space or punctuation)
    if original_trimmed and original_trimmed[-1].isalnum():
        # Mid-word truncation - direct concatenation
        return original_trimmed + continuation_trimmed

    # Check if original ends mid-sentence (no period/question/exclamation)
    sentence_endings = (".", "!", "?", "```", "}", "]", ")", '"')
    if original_trimmed and not original_trimmed.endswith(sentence_endings):
        # Mid-sentence - add space
        return original_trimmed + " " + continuation_trimmed

    # Complete sentence/block - add newline
    return original_trimmed + "\n\n" + continuation_trimmed
