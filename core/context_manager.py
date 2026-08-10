# core/context_manager.py

"""
Smart context management - reads pre-computed token estimates
Much faster - no recalculation at query time
"""

from dataclasses import dataclass
from datetime import datetime

from core.config import get_config
from core.db_connection import get_db_connection
from core.token_estimator import estimate_messages


@dataclass
class FileContext:
    """File with pre-computed token count"""

    file_path: str
    estimated_tokens: int  # Read from database
    priority_score: float
    metadata: dict


class ContextManager:
    """
    Smart context manager - uses pre-computed token estimates

    Philosophy:
    - Token counts computed once at write time (init, file mod)
    - Context building is just reading and sorting
    - Fast enough to run every iteration
    """

    def __init__(self):
        self.config = get_config()

        # Build model limits from config (with safety factor)
        self.model_limits = {}
        models_config = self.config.get("models", {})

        for model_name, model_config in models_config.items():
            # Get context window size
            max_context = model_config.get("max_context_tokens")
            max_output = model_config.get("max_output_tokens", 16384)

            if max_context:
                # Reserve space for output + safety margin (80% of available)
                usable_input = int((max_context - max_output) * 0.8)
                self.model_limits[model_name] = usable_input
            else:
                # Fallback: conservative default if not specified
                self.model_limits[model_name] = 100_000

        # Fallback for unknown models
        self.default_context_limit = 100_000

    def get_model_context_limit(self, model: str) -> int:
        """Get context limit for model from config-driven limits"""

        # Try model-specific limit
        if model in self.model_limits:
            return self.model_limits[model]

        # Try to compute from config on-the-fly
        models_config = self.config.get("models", {})
        if model in models_config:
            model_config = models_config[model]
            max_context = model_config.get("max_context_tokens")
            max_output = model_config.get("max_output_tokens", 16384)

            if max_context:
                return int((max_context - max_output) * 0.8)

        # Conservative default for unknown models
        print(f"⚠️  Unknown model '{model}', using default context limit")
        return self.default_context_limit

    def build_orchestrator_context(
        self,
        task_id: str,
        user_command: str,
        conversation_history: list[dict],
        model: str | None = None,
    ) -> tuple[str, dict]:
        """
        Build context for orchestrator using pre-computed token counts.
        FAST - just reads from database, no recalculation.
        """
        context_limit = self.get_model_context_limit(model)

        # 1. Count all non-binary files across all subdirectories
        total_project_files = 0
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM project_files
                    WHERE is_binary = 0
                      AND file_path NOT LIKE '.PrizmForge/%'
                      AND file_path NOT LIKE '.git/%'
                """
                )
                row = cursor.fetchone()
                total_project_files = row[0] if row else 0
        except Exception as e:
            print(f"⚠️ Failed to query project_files count: {e}")
            total_project_files = 0

        # Base prompt
        base_context = f"**Task:** {user_command}\n\n"
        base_tokens = len(base_context) // 4  # Quick estimate

        # Conversation history tokens
        history_tokens = estimate_messages(conversation_history)

        # Get prioritized suggestions
        prioritized_msg = self._get_prioritized_suggestions(task_id)
        priority_tokens = 0
        if prioritized_msg:
            priority_tokens = len(prioritized_msg) // 4
            base_context += prioritized_msg + "\n\n"

        # Structural index from target .PrizmForge/indexes
        index_tokens = 0
        try:
            from core.index_context import build_index_context_block

            index_block = build_index_context_block(max_chars=8_000)
            if index_block and "not available" not in index_block:
                index_tokens = len(index_block) // 4
                base_context += index_block + "\n"
        except Exception as e:
            print(f"    ⚠️  Exception handled in context_manager.py: {e}")

        tokens_used = base_tokens + history_tokens + priority_tokens + index_tokens

        # Reserve 5% for system prompt + response
        available_for_files = int(context_limit * 0.95) - tokens_used

        # Early return if context budget is exhausted
        if available_for_files < 1000:
            return base_context, {
                "tokens_used": tokens_used,
                "tokens_available": 0,
                "context_limit": context_limit,
                "context_utilization": tokens_used / context_limit if context_limit else 0,
                "total_project_files": total_project_files,
                "files_included": [],
                "files_excluded": "all",
                "truncation_reason": "No budget for files",
            }

        # Read pre-computed token estimates from database
        file_contexts = self._get_prioritized_files_fast(task_id)

        # Pack files until context limit is reached
        included_files = []
        excluded_files = []
        remaining_budget = available_for_files

        file_section = "**📁 Project Files:**\n\n"

        for fc in file_contexts:
            if fc.estimated_tokens <= remaining_budget:
                file_section += self._format_file_summary(fc) + "\n"
                included_files.append(
                    {
                        "path": fc.file_path,
                        "tokens": fc.estimated_tokens,
                        "priority": fc.priority_score,
                    }
                )
                remaining_budget -= fc.estimated_tokens
                tokens_used += fc.estimated_tokens
            else:
                excluded_files.append(
                    {
                        "path": fc.file_path,
                        "tokens": fc.estimated_tokens,
                        "reason": "Exceeded budget",
                    }
                )

        # Add file summary line
        file_section += f"\n*Included {len(included_files)} files "
        file_section += f"({tokens_used:,} / {context_limit:,} tokens, "
        file_section += f"{tokens_used / context_limit:.1%} utilization)*\n"

        if excluded_files:
            file_section += f"*Excluded {len(excluded_files)} files (insufficient budget)*\n"

        final_context = base_context + file_section

        # Final metadata dictionary passed to callers
        metadata = {
            "tokens_used": tokens_used,
            "tokens_available": max(0, context_limit - tokens_used),
            "context_limit": context_limit,
            "context_utilization": tokens_used / context_limit if context_limit else 0,
            "total_project_files": total_project_files,  # Total non-binary count across all subdirectories
            "files_included": included_files,
            "files_excluded": excluded_files,
            "truncation_reason": "Budget limit" if excluded_files else "All files fit",
        }

        return final_context, metadata

    def _get_prioritized_files_fast(self, task_id: str, limit: int = 100) -> list[FileContext]:
        """
        Get prioritized files with PRE-COMPUTED token estimates
        FAST - just one query with sorting

        UPDATED: Added limit parameter to prevent OOM
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Single query - reads pre-computed tokens
                cursor.execute(
                    """
                    SELECT
                        pf.file_path,
                        pf.estimated_tokens,
                        pf.last_modified,
                        pf.size_bytes,
                        fs.purpose,
                        fs.line_count,
                        COUNT(DISTINCT af.id) as issue_count,
                        MAX(af.timestamp) as last_issue
                    FROM project_files pf
                    LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                    LEFT JOIN agent_feedback af ON pf.file_path = af.file_path
                        AND af.addressed = 0
                    WHERE pf.is_binary = 0 AND pf.estimated_tokens > 0
                    GROUP BY pf.file_path
                    ORDER BY pf.last_modified DESC
                    LIMIT ?
                """,
                    (limit,),
                )  # ✅ ADDED LIMIT

                rows = cursor.fetchall()

            file_contexts = []

            for row in rows:
                (
                    file_path,
                    estimated_tokens,
                    last_modified,
                    size_bytes,
                    purpose,
                    line_count,
                    issue_count,
                    _last_issue,
                ) = row

                # Calculate priority score
                priority_score = self._calculate_priority(file_path, last_modified, issue_count, size_bytes)

                file_contexts.append(
                    FileContext(
                        file_path=file_path,
                        estimated_tokens=estimated_tokens,  # Pre-computed!
                        priority_score=priority_score,
                        metadata={
                            "purpose": purpose,
                            "line_count": line_count,
                            "issue_count": issue_count,
                        },
                    )
                )

            # Sort by priority descending
            file_contexts.sort(key=lambda fc: fc.priority_score, reverse=True)

            return file_contexts

        except Exception as e:
            print(f"⚠️  Error loading files: {e}")
            return []

    def _calculate_priority(self, file_path: str, last_modified: str, issue_count: int, size_bytes: int) -> float:
        """Calculate priority score"""
        score = 0.0

        # Recently modified (+50 points)
        try:
            mod_time = datetime.fromisoformat(last_modified)
            age_hours = (datetime.now() - mod_time).total_seconds() / 3600
            if age_hours < 1:
                score += 50
            elif age_hours < 24:
                score += 30
            elif age_hours < 168:
                score += 10
        except Exception as e:
            print(f"    ⚠️  Exception handled in context_manager.py: {e}")

        # Has issues (+30 per issue, max 60)
        score += min(issue_count * 30, 60)

        # Small files preferred (+20 if < 5KB)
        if size_bytes < 5000:
            score += 20

        # Core files (+25)
        core_indicators = ["main", "config", "init", "__init__", "app", "index"]
        if any(ind in file_path.lower() for ind in core_indicators):
            score += 25

        # Python files (+5)
        if file_path.endswith(".py"):
            score += 5

        return score

    def _format_file_summary(self, fc: FileContext) -> str:
        """Format file summary for context"""
        purpose = fc.metadata.get("purpose", "")
        line_count = fc.metadata.get("line_count", 0)
        issue_count = fc.metadata.get("issue_count", 0)

        summary = f"• **{fc.file_path}**"

        if line_count:
            summary += f" ({line_count} lines, ~{fc.estimated_tokens} tokens)"

        if purpose:
            summary += f"\n  {purpose}"

        if issue_count > 0:
            summary += f"\n  ⚠️  {issue_count} unresolved issue(s)"

        return summary

    def _get_prioritized_suggestions(self, task_id: str) -> str | None:
        """
        Get prioritized suggestions from agent_feedback and proposals
        Shows ALL unaddressed items in priority order
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get ALL unaddressed feedback (prioritized)
                cursor.execute(
                    """
                    SELECT id, agent_name, file_path, priority, category, message, suggestion
                    FROM agent_feedback
                    WHERE task_id = ? AND addressed = 0
                    ORDER BY
                        CASE priority
                            WHEN 'CRITICAL' THEN 1
                            WHEN 'HIGH' THEN 2
                            WHEN 'MEDIUM' THEN 3
                            ELSE 4
                        END,
                        timestamp DESC
                    LIMIT 20
                """,
                    (task_id,),
                )

                feedback_items = cursor.fetchall()

                # Get pending proposals
                cursor.execute(
                    """
                    SELECT proposal_id, target_file_path, status, rationale
                    FROM edit_proposals
                    WHERE status IN ('pending', 'under_review', 'approved')
                    ORDER BY created_at DESC
                    LIMIT 5
                """
                )

                proposals = cursor.fetchall()

                # Build summary message
                if not feedback_items and not proposals:
                    return None

                message = "📋 **ACTIONABLE ITEMS (Priority Order):**\n\n"

                if feedback_items:
                    # Count by priority
                    priority_counts = {}
                    for item in feedback_items:
                        priority = item[3]
                        priority_counts[priority] = priority_counts.get(priority, 0) + 1

                    summary = ", ".join([f"{count} {priority}" for priority, count in sorted(priority_counts.items())])
                    message += f"**🔴 Unaddressed Feedback: {len(feedback_items)} items ({summary})**\n\n"

                    # Show top 10 items
                    for i, (
                        fid,
                        _agent,
                        fpath,
                        priority,
                        category,
                        msg,
                        suggestion,
                    ) in enumerate(feedback_items[:10], 1):
                        message += f"{i}. **[{priority}]** {category} in `{fpath}` (ID: {fid})\n"
                        message += f"   {msg[:80]}{'...' if len(msg) > 80 else ''}\n"
                        if suggestion:
                            message += f"   💡 {suggestion[:60]}{'...' if len(suggestion) > 60 else ''}\n"

                    if len(feedback_items) > 10:
                        message += f"\n   _(+{len(feedback_items) - 10} more items in backlog)_\n"
                    message += "\n"

                if proposals:
                    message += f"**📄 Pending Proposals ({len(proposals)}):**\n"
                    for prop_id, fpath, status, rationale in proposals:
                        message += f"• {prop_id[:8]}... → `{fpath}` ({status})\n"
                        if rationale:
                            message += f"  {rationale[:60]}{'...' if len(rationale) > 60 else ''}\n"

                return message

        except Exception as e:
            print(f"    ⚠️  Error getting prioritized suggestions: {e}")
            return None


# =============================================================================
# Global Singleton
# =============================================================================

_context_manager = None


def get_context_manager() -> ContextManager:
    """Get global context manager instance"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
