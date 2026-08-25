"""Prioritizer worker - intelligent multi-phase feedback processing"""

import logging
import re
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime

from agents.base import call_agent
from core.config import get_config
from core.db_connection import get_db_connection
from core.db_helpers import post_message
from core.index_context import load_index_text, load_symbol_json_context
from core.json_parser import parse_json_response

logger = logging.getLogger(__name__)


def _phase_model_override(phase: str) -> str | None:
    """Model id for prioritizer phases from config (never hardcode provider names).

    batch: categorizing / scoring batches → resource_controller.model_downgrades.prioritizer_batch
           (falls back to default_model).
    rank:  cross-category ranking → agent_model_preferences.prioritizer
           (falls back to default_model).
    """
    cfg = get_config()
    md = (cfg.get("resource_controller") or {}).get("model_downgrades") or {}
    if phase == "batch":
        return md.get("prioritizer_batch") or md.get("default_model")
    if phase == "rank":
        prefs = cfg.get("agent_model_preferences") or {}
        return prefs.get("prioritizer") or md.get("default_model")
    return None


@dataclass
class FeedbackItem:
    """Feedback item with metadata"""

    id: str
    from_agent: str
    file_path: str
    priority: str
    category: str
    message: str
    suggestion: str
    timestamp: str
    raw_id: int = 0
    item_type: str = "feedback"
    bias_multiplier: float = 1.0
    score: float = 0.0


class PrioritizerWorker:
    """
    Multi-phase intelligent prioritizer

    Phase 1: Categorize uncategorized items (batches of 30)
    Phase 2: Score within categories
    Phase 3: Cross-category prioritization
    Phase 4: Output top N to orchestrator
    """

    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.current_task_id = None
        self.last_prioritization = None
        self.prioritization_interval = 20  # Check every 20s
        self.processing_cycle_time = 0  # Time of last full cycle

        # Circuit breaker (soak P2: endpoint outages turned each cycle into a
        # burst of failing batch calls, ~1,071 errors in 12h). The breaker is
        # a backstop only: per-model down windows + round-robin rotation do
        # the real resilience work, so cooldown stays short.
        self.consecutive_batch_failures = 0
        self.max_consecutive_batch_failures = 3
        self.circuit_open_until = 0.0
        self.circuit_cooldown_seconds = 120

        # Round-robin model rotation: on batch failure advance to the next
        # healthy candidate (any endpoint) instead of re-dialing the same one.
        self._rr_index = 0
        self._rr_override: str | None = None

    def start(self, task_id: str):
        """Start the prioritizer worker"""
        if self.running:
            return

        self.running = True
        self.current_task_id = task_id
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="prioritizer-worker")
        self.worker_thread.start()
        print("    🎯 Started prioritizer worker (multi-phase intelligent)")

    def stop(self):
        """Stop the prioritizer worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        print("    🎯 Stopped prioritizer worker")

    def _worker_loop(self):
        """Main worker loop - wait for full cycle before starting timer"""
        while self.running:
            try:
                time.sleep(5)  # Check every 5 seconds

                if not self.running:
                    break

                # Check if we should run a full cycle
                if self._should_run_cycle():
                    print("\n    🎯 ━━━ PRIORITIZER CYCLE START ━━━")
                    self._run_full_prioritization_cycle()
                    self.processing_cycle_time = time.time()
                    print("    🎯 ━━━ PRIORITIZER CYCLE COMPLETE ━━━\n")
                    self.last_prioritization = time.time()

            except Exception as e:
                print(f"    ⚠️  Prioritizer error: {e}")

                traceback.print_exc()
                time.sleep(30)

    def _filter_low_quality_feedback(self, items: list[FeedbackItem]) -> tuple[list[FeedbackItem], int]:
        """
        Filter out and auto-dismiss low-quality feedback.
        Returns (valid_items, dismissed_count)
        """
        low_quality_patterns = [
            # Placeholder text
            r"^issue here$",
            r"^fix here$",
            r"^todo",
            r"^placeholder",
            # Too generic
            r"^issue$",
            r"^bug$",
            r"^error$",
            # Too short (less than 15 chars)
            r"^.{1,14}$",
            # Just variable names
            r"^[a-z_]+$",
        ]

        valid_items = []
        dismissed_items = []

        for item in items:
            # Check message quality
            message_lower = item.message.lower().strip()
            suggestion_lower = (item.suggestion or "").lower().strip()

            is_low_quality = False
            reason = None

            # Pattern matching
            for pattern in low_quality_patterns:
                if re.match(pattern, message_lower, re.IGNORECASE):
                    is_low_quality = True
                    reason = f"Generic placeholder: '{item.message[:30]}'"
                    break

            # Check if both message and suggestion are placeholders
            if not is_low_quality:
                if message_lower in [
                    "issue here",
                    "todo",
                    "fix this",
                ] and suggestion_lower in ["fix here", "todo", "fix this"]:
                    is_low_quality = True
                    reason = "Both message and suggestion are placeholders"

            # Check if message is just repeating the category
            if not is_low_quality:
                if message_lower == item.category.lower():
                    is_low_quality = True
                    reason = f"Message just repeats category: '{item.category}'"

            if is_low_quality:
                dismissed_items.append((item, reason))
            else:
                valid_items.append(item)

        # Auto-dismiss low quality items in database
        if dismissed_items:
            try:
                with get_db_connection() as conn:
                    for item, reason in dismissed_items:
                        if item.item_type == "feedback":
                            conn.execute(
                                """
                                UPDATE agent_feedback
                                SET addressed = 1,
                                    addressed_by = 'prioritizer_quality_filter',
                                    addressed_at = ?
                                WHERE id = ?
                            """,
                                (datetime.now().isoformat(), item.raw_id),
                            )
                        elif item.item_type == "message":
                            conn.execute(
                                """
                                UPDATE messages
                                SET read = 1
                                WHERE id = ?
                            """,
                                (item.raw_id,),
                            )

                        print(f"    🗑️  Dismissed {item.item_type} #{item.id}: {reason}")
            except Exception as e:
                print(f"    ⚠️  Failed to dismiss low-quality feedback: {e}")

        return valid_items, len(dismissed_items)

    def _should_run_cycle(self) -> bool:
        """Check if we should run a prioritization cycle"""
        # First cycle - always run
        if self.processing_cycle_time == 0:
            return True

        # Check if interval elapsed since last cycle
        if self.last_prioritization is None:
            return True

        elapsed = time.time() - self.last_prioritization
        return elapsed >= self.prioritization_interval

    def _run_full_prioritization_cycle(self):
        """
        Full multi-phase prioritization cycle

        Phase 1: Filter low-quality feedback
        Phase 2: Categorize uncategorized items
        Phase 3: Score within categories
        Phase 4: Cross-category ranking
        Phase 5: Post to orchestrator
        """
        # Circuit breaker: while cooling down after repeated batch failures,
        # don't fully idle — the cycle continues in probe mode (one batch).
        probe_mode = time.time() < self.circuit_open_until
        if probe_mode:
            remaining = int(self.circuit_open_until - time.time())
            print(f"    ⚡ Prioritizer circuit open — cooldown {remaining}s remaining (probe mode)")

        # Get all feedback
        all_feedback = self._get_all_feedback()

        if not all_feedback:
            print("    📊 No feedback to prioritize")
            return

        print(f"    📊 Processing {len(all_feedback)} feedback items")

        # Phase 1: Quality filter
        valid_feedback, dismissed_count = self._filter_low_quality_feedback(all_feedback)

        if dismissed_count > 0:
            print(f"    🗑️  Phase 1: Dismissed {dismissed_count} low-quality items")
            print(f"    📊 Remaining: {len(valid_feedback)} valid items")

        if not valid_feedback:
            print("    ✅ No valid feedback remaining after quality filter")
            return

        # Phase 2: Categorize uncategorized (batches of 30)
        categorized = self._categorize_feedback(valid_feedback, probe_mode=probe_mode)

        if not categorized:
            print("    ✓ Phase 2: All items categorized")

        # Phase 3: Score within categories
        scored_by_category = self._score_within_categories(categorized)

        # Phase 4: Cross-category prioritization
        final_ranked = self._cross_category_ranking(scored_by_category)

        # Phase 5: Post to orchestrator
        self._post_results(final_ranked)

    def _get_all_feedback(self) -> list[FeedbackItem]:
        """Get ALL unaddressed feedback (no limit)"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get ALL unaddressed feedback
                cursor.execute(
                    """
                    SELECT
                        id, agent_name, file_path, priority, category,
                        message, suggestion, timestamp
                    FROM agent_feedback
                    WHERE task_id = ?
                    AND addressed = 0
                    ORDER BY timestamp DESC
                """,
                    (self.current_task_id,),
                )

                feedback_rows = cursor.fetchall()

                # Get unread messages
                cursor.execute(
                    """
                    SELECT
                        id, from_agent, content, priority, timestamp
                    FROM messages
                    WHERE task_id = ?
                    AND to_agent = 'orchestrator'
                    AND read = 0
                    ORDER BY timestamp DESC
                """,
                    (self.current_task_id,),
                )

                message_rows = cursor.fetchall()

            items = []

            # Convert feedback — namespace id as fb_N to avoid collisions with messages
            for row in feedback_rows:
                bias = 5.0 if row[1] == "human" else 1.0

                items.append(
                    FeedbackItem(
                        id=f"fb_{row[0]}",
                        raw_id=row[0],
                        item_type="feedback",
                        from_agent=row[1],
                        file_path=row[2],
                        priority=row[3] or "MEDIUM",
                        category=row[4] or "uncategorized",
                        message=row[5],
                        suggestion=row[6] or "",
                        timestamp=row[7],
                        bias_multiplier=bias,
                    )
                )

            # Convert messages — namespace id as msg_N
            for row in message_rows:
                bias = 5.0 if row[1] == "human" else 1.0
                items.append(
                    FeedbackItem(
                        id=f"msg_{row[0]}",
                        raw_id=row[0],
                        item_type="message",
                        from_agent=row[1],
                        file_path="<message>",
                        priority=row[3] or "MEDIUM",
                        category="message",
                        message=row[2],
                        suggestion="",
                        timestamp=row[4],
                        bias_multiplier=bias,
                    )
                )

            return items

        except Exception as e:
            print(f"    ❌ Error getting feedback: {e}")
            return []

    def _categorize_feedback(self, items: list[FeedbackItem], probe_mode: bool = False) -> list[FeedbackItem]:
        """Phase 1: Categorize uncategorized items in batches of 30"""
        uncategorized = [item for item in items if item.category == "uncategorized"]

        if not uncategorized:
            print("    ✓ Phase 1: All items categorized")
            return items

        print(f"    → Phase 1: Categorizing {len(uncategorized)} items (batches of 30)")

        # While the circuit is open we don't idle: run a single probe batch
        # (round-robin may land on a recovered model). A successful probe
        # resets the failure counter and reopens the gate for later cycles.
        probe_only = probe_mode
        if probe_only:
            print("    ⚡ Circuit open — probing with a single batch")

        # Process in batches of 30, with a circuit breaker: after N
        # consecutive failed batches (endpoint outage), stop hammering and
        # open a cooldown before the next cycle may retry.
        for i in range(0, len(uncategorized), 30):
            batch = uncategorized[i : i + 30]
            ok = self._categorize_batch(batch)
            if ok:
                self.consecutive_batch_failures = 0
                self.circuit_open_until = 0.0
                self._rr_override = None  # healthy again → default phase model
                if probe_only:
                    break
            else:
                self.consecutive_batch_failures += 1
                # Rotate to the next candidate instead of re-dialing the same
                # model; per-model down windows make the skip authoritative.
                nxt = self._rr_next_model()
                if nxt and nxt != self._rr_override:
                    print(f"    🔄 Rotating categorization model → {nxt}")
                    self._rr_override = nxt
                backoff = min(5 * (2 ** (self.consecutive_batch_failures - 1)), 60)
                print(
                    f"    ⚡ Categorization failed ({self.consecutive_batch_failures}"
                    f"/{self.max_consecutive_batch_failures} consecutive) — backing off {backoff}s"
                )
                time.sleep(backoff)
                if self.consecutive_batch_failures >= self.max_consecutive_batch_failures:
                    self.circuit_open_until = time.time() + self.circuit_cooldown_seconds
                    remaining_batches = (len(uncategorized) - i - 30) // 30 + (1 if (len(uncategorized) - i - 30) % 30 else 0)
                    print(f"    ⚡ Circuit OPEN for {self.circuit_cooldown_seconds}s — aborting {remaining_batches} remaining batch(es)")
                    break

            if probe_only:
                break  # failed or succeeded: a probe is exactly one batch        print("    ✓ Phase 1: Complete")
        return items

    def _rr_next_model(self) -> str | None:
        """Advance the round-robin cursor and return an "endpoint/model" override.

        Candidates are all configured models across available endpoints,
        ordered by model-health (healthy first, demoted next, down last), so
        after a failure the next attempt lands on a *different* model — and
        when rotation wraps back to the original endpoint, its sibling model
        is picked because the failed one is marked down.
        """
        try:
            from core.endpoint_manager import get_endpoint_manager

            mgr = get_endpoint_manager()
            candidates: list[tuple[str, int]] = []
            for ep in sorted(mgr.get_available_endpoints(), key=lambda e: e.priority):
                for key in mgr.models:
                    if key.startswith(f"{ep.name}/"):
                        candidates.append((key, ep.priority or 0))
            if not candidates:
                return None
            try:
                from core.model_health import model_down_until, rank_candidates

                candidates = rank_candidates(candidates)
                # Skip currently-down models while any healthy one exists;
                # if ALL are down, keep the list so rotation can probe.
                live = [c for c in candidates if not model_down_until(c[0])]
                candidates = live or candidates
            except Exception:
                candidates.sort(key=lambda c: c[1])
            ref = candidates[self._rr_index % len(candidates)][0]
            self._rr_index += 1
            return ref
        except Exception as e:
            logger.debug(f"round-robin candidate selection skipped: {e}")
            return None

    def _categorize_batch(self, batch: list[FeedbackItem]):
        """Categorize a batch of items. Returns True on success."""
        # Build prompt with message and suggestion context
        index_snip = ""
        try:
            paths = [getattr(it, "file_path", None) for it in batch]
            paths = [p for p in paths if p]
            index_snip = load_symbol_json_context(
                file_paths=paths or None,
                max_rows=40,
                label="Known symbols near feedback paths",
            )
            if not index_snip.strip():
                raw = load_index_text(which="production", max_chars=4_000)
                if raw.strip():
                    index_snip = "Known source paths (Markdown fallback):\n" + raw + "\n\n"
            elif not index_snip.endswith("\n"):
                index_snip += "\n"
        except Exception as e:
            print(f"    ⚠️  Exception handled in prioritizer_worker.py: {e}")
        prompt = f"{index_snip}Categorize these {len(batch)} feedback items:\n\n"
        for idx, item in enumerate(batch, 1):
            prompt += f"#{idx} (ID: {item.id})\n"
            prompt += f"From: {item.from_agent}\n"
            prompt += f"File: {item.file_path}\n"
            prompt += f"Priority: {item.priority}\n"
            prompt += f"Message: {item.message[:200]}\n"
            if item.suggestion:
                prompt += f"Suggestion: {item.suggestion[:200]}\n"
            prompt += "\n"

        prompt += """
Categories: security, bug, performance, maintainability, documentation, architecture, style, other

Respond with JSON ONLY:
{
  "categorized": [
    {"id": "fb_1", "category": "security"},
    {"id": "fb_2", "category": "bug"}
  ]
}
"""

        try:
            response = call_agent(
                "prioritizer",
                prompt,
                self.current_task_id,
                model_override=self._rr_override or _phase_model_override("batch"),
            )

            if not response:
                return False

            data = parse_json_response(
                response,
                expected_keys=["categorized"],
                agent_name="prioritizer/categorize",
            )

            if data and "categorized" in data:
                self._update_categories(data["categorized"])
                return True

            return False

        except Exception as e:
            print(f"    ⚠️  Categorization batch error: {e}")
            return False

    def _update_categories(self, categorized: list[dict]):
        """Update categories in database (feedback rows only)."""
        try:
            with get_db_connection() as conn:
                for item in categorized:
                    item_id_str = str(item["id"])
                    if item_id_str.startswith("msg_"):
                        continue
                    if item_id_str.startswith("fb_"):
                        raw_id = int(item_id_str.replace("fb_", "", 1))
                    else:
                        raw_id = int(item["id"])
                    conn.execute(
                        """
                        UPDATE agent_feedback
                        SET category = ?
                        WHERE id = ?
                    """,
                        (item["category"], raw_id),
                    )
        except Exception as e:
            print(f"    ⚠️  Error updating categories: {e}")

    def _score_within_categories(self, items: list[FeedbackItem]) -> dict[str, list[FeedbackItem]]:
        """Phase 2: Score items within each category"""
        print("    → Phase 2: Scoring within categories")

        # Group by category
        by_category = {}
        for item in items:
            if item.category not in by_category:
                by_category[item.category] = []
            by_category[item.category].append(item)

        # Score within each category
        for category, category_items in by_category.items():
            self._score_category(category, category_items)

        print(f"    ✓ Phase 2: Scored {len(by_category)} categories")
        return by_category

    def _score_category(self, category: str, items: list[FeedbackItem]):
        """Score items within a category"""
        # Build scoring request
        prompt = f"Score these {len(items)} {category} items (0-100):\n\n"
        for item in items:
            prompt += f"ID: {item.id} | Priority: {item.priority} | From: {item.from_agent}\n"
            prompt += f"Message: {item.message[:150]}\n\n"
        prompt += """
Consider:
- Severity/Impact
- Actionability
- Specificity

Respond with JSON ONLY:
{
  "scored": [
    {"id": "fb_1", "score": 85},
    {"id": "fb_2", "score": 60}
  ]
}
"""
        try:
            response = call_agent(
                "prioritizer",
                prompt,
                self.current_task_id,
                model_override=_phase_model_override("batch"),
            )

            if not response:
                return

            data = parse_json_response(response, expected_keys=["scored"], agent_name="prioritizer/categorize")

            if data and "scored" in data:
                score_map = {str(s["id"]): s["score"] for s in data["scored"]}
                for item in items:
                    if item.id in score_map:
                        item.score = score_map[item.id]
                    elif str(item.raw_id) in score_map:
                        item.score = score_map[str(item.raw_id)]

        except Exception as e:
            print(f"    ⚠️  Category scoring error: {e}")

    def _top_by_score(self, items: list[FeedbackItem], limit: int = 8) -> list[FeedbackItem]:
        """Deterministic fallback ranking when the ranking LLM is unavailable."""
        return sorted(items, key=lambda x: x.score, reverse=True)[:limit]

    def _cross_category_ranking(self, by_category: dict[str, list[FeedbackItem]]) -> list[FeedbackItem]:
        """Phase 3: Cross-category prioritization"""
        print("    → Phase 3: Cross-category ranking")

        # Flatten all items with scores
        all_items = []
        for items in by_category.values():
            all_items.extend(items)

        # Build final ranking request (metadata only)
        prompt = f"Final ranking of top {min(len(all_items), 50)} items:\n\n"

        # Sort by score desc, take top 50
        top_items = sorted(all_items, key=lambda x: x.score, reverse=True)[:50]

        for item in top_items:
            prompt += f"ID: {item.id} | Priority: {item.priority} | Category: {item.category} | "
            prompt += f"Bias: {item.bias_multiplier}x | Score: {item.score}\n"

        prompt += """
Apply final bias and rank. Output TOP 8 ONLY.

Respond with JSON ONLY:
{
  "top_suggestions": [
    {
      "id": "fb_123",
      "final_score": 150,
      "rank": 1,
      "action_for_orchestrator": "Fix critical security issue in X"
    }
  ]
}
"""

        try:
            response = call_agent(
                "prioritizer",
                prompt,
                self.current_task_id,
                model_override=_phase_model_override("rank"),
            )

            # Empty / None response: same deterministic fallback as exception path
            if not response:
                return self._top_by_score(all_items)

            data = parse_json_response(
                response,
                expected_keys=["top_suggestions"],
                agent_name="prioritizer/categorize",
            )

            if data and "top_suggestions" in data:
                id_map = {item.id: item for item in all_items}
                raw_id_map = {str(item.raw_id): item for item in all_items}
                ranked = []
                for suggestion in data["top_suggestions"][:8]:
                    item_id = str(suggestion["id"])
                    item = id_map.get(item_id) or raw_id_map.get(item_id)
                    if item:
                        item.score = suggestion.get("final_score", item.score)
                        ranked.append(item)

                print(f"    ✓ Phase 3: Ranked top {len(ranked)} items")
                return ranked

        except Exception as e:
            print(f"    ⚠️  Cross-category ranking error: {e}")

        # Fallback: return top 8 by score
        return self._top_by_score(all_items)

    def _post_results(self, ranked: list[FeedbackItem]):
        """Phase 4: Post to orchestrator"""
        if not ranked:
            return

        print(f"    → Phase 4: Posting top {len(ranked)} to orchestrator")

        # Build message
        message = f"🎯 **PRIORITIZED FEEDBACK** ({len(ranked)} items)\n\n"

        for idx, item in enumerate(ranked, 1):
            icon = "⭐" if item.from_agent == "human" else "🔹"
            message += f"{icon} **#{idx}** [{item.priority}] {item.category}\n"
            message += f"   File: {item.file_path}\n"
            message += f"   {item.message[:100]}\n"
            if item.suggestion:
                message += f"   💡 {item.suggestion[:100]}\n"
            message += f"   Score: {item.score:.0f}\n\n"

        # Post to orchestrator
        post_message("prioritizer", "orchestrator", message, self.current_task_id, "HIGH")

        # Mark items as read
        self._mark_items_processed(ranked)

        print("    ✓ Phase 4: Posted to orchestrator")

    def _mark_items_processed(self, items: list[FeedbackItem]):
        """Mark items as READ (not addressed - that happens when developer fixes them)"""
        try:
            with get_db_connection() as conn:
                for item in items:
                    if item.item_type == "message" or item.file_path == "<message>":
                        conn.execute("UPDATE messages SET read = 1 WHERE id = ?", (item.raw_id,))
                    else:
                        # Only mark messages as read; feedback stays unaddressed
                        # until the developer actually fixes it
                        pass
        except Exception as e:
            print(f"    ⚠️  Error marking processed: {e}")


# Global singleton
_prioritizer_worker = None


def get_prioritizer_worker() -> PrioritizerWorker:
    """Get global prioritizer worker"""
    global _prioritizer_worker
    if _prioritizer_worker is None:
        _prioritizer_worker = PrioritizerWorker()
    return _prioritizer_worker
