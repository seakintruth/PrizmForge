"""
Smart context management - reads pre-computed token estimates
Much faster - no recalculation at query time
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from core.db import get_db_path
from core.config import get_config
from core.token_estimator import estimate_messages
from core.db_connection import get_db_connection

@dataclass
class FileContext:
    """File with pre-computed token count"""
    file_path: str
    estimated_tokens: int  # Read from database
    priority_score: float
    metadata: Dict


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
        
        # Model context limits (conservative estimates)
        self.model_limits = {
            "gemini-2.0-flash-exp": int(1_000_000 * 0.8),
            "gemini-1.5-pro": int(2_000_000 * 0.8),
            "gemini-1.5-flash": int(1_000_000 * 0.8),
            "gemini-3.1-pro-preview": int(2_000_000 * 0.8),
            "gemini-3-flash-preview": int(1_000_000 * 0.8),
            "gemini-2.5-pro": int(2_000_000 * 0.8),
            "databricks-claude-sonnet-4-5": int(200_000 * 0.8),
        }
    
    def get_model_context_limit(self, model: str) -> int:
        """Get context limit for model"""
        if model in self.model_limits:
            return self.model_limits[model]
        
        # Try config
        model_config = self.config.get("models", {}).get(model, {})
        max_output = model_config.get("max_output_tokens", 16384)
        
        # Conservative default: 100K input
        return 100_000 - max_output
    
    def build_orchestrator_context(
        self, 
        task_id: str,
        user_command: str,
        conversation_history: List[Dict],
        model: str = None
    ) -> Tuple[str, Dict]:
        """
        Build context for orchestrator using pre-computed token counts
        FAST - just reads from database, no recalculation
        """
        context_limit = self.get_model_context_limit(model)
        
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
        
        tokens_used = base_tokens + history_tokens + priority_tokens
        
        # Reserve 5% for system prompt + response
        available_for_files = int(context_limit * 0.95) - tokens_used
        
        if available_for_files < 1000:
            return base_context, {
                "tokens_used": tokens_used,
                "tokens_available": 0,
                "context_limit": context_limit,
                "files_included": [],
                "files_excluded": "all",
                "truncation_reason": "No budget for files"
            }
        
        # ============= FAST: Read pre-computed tokens from database =============
        file_contexts = self._get_prioritized_files_fast(task_id)
        # ========================================================================
        
        # Pack files until we hit limit
        included_files = []
        excluded_files = []
        remaining_budget = available_for_files
        
        file_section = "**📁 Project Files:**\n\n"
        
        for fc in file_contexts:
            if fc.estimated_tokens <= remaining_budget:
                # Include
                file_section += self._format_file_summary(fc) + "\n"
                included_files.append({
                    "path": fc.file_path,
                    "tokens": fc.estimated_tokens,
                    "priority": fc.priority_score
                })
                remaining_budget -= fc.estimated_tokens
                tokens_used += fc.estimated_tokens
            else:
                # Exclude
                excluded_files.append({
                    "path": fc.file_path,
                    "tokens": fc.estimated_tokens,
                    "reason": "Exceeded budget"
                })
        
        # Add summary
        file_section += f"\n*Included {len(included_files)} files "
        file_section += f"({tokens_used:,} / {context_limit:,} tokens, "
        file_section += f"{tokens_used/context_limit:.1%} utilization)*\n"
        
        if excluded_files:
            file_section += f"*Excluded {len(excluded_files)} files (insufficient budget)*\n"
        
        final_context = base_context + file_section
        
        metadata = {
            "tokens_used": tokens_used,
            "tokens_available": context_limit - tokens_used,
            "context_limit": context_limit,
            "context_utilization": tokens_used / context_limit,
            "files_included": included_files,
            "files_excluded": excluded_files,
            "truncation_reason": "Budget limit" if excluded_files else "All files fit"
        }
        
        return final_context, metadata
    
    def _get_prioritized_files_fast(self, task_id: str) -> List[FileContext]:
        """
        Get prioritized files with PRE-COMPUTED token estimates
        FAST - just one query with sorting
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Single query - reads pre-computed tokens
                cursor.execute("""
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
                """)
                
                rows = cursor.fetchall()
            
            file_contexts = []
            
            for row in rows:
                file_path, estimated_tokens, last_modified, size_bytes, purpose, line_count, issue_count, last_issue = row
                
                # Calculate priority score
                priority_score = self._calculate_priority(
                    file_path, last_modified, issue_count, size_bytes
                )
                
                file_contexts.append(FileContext(
                    file_path=file_path,
                    estimated_tokens=estimated_tokens,  # Pre-computed!
                    priority_score=priority_score,
                    metadata={
                        "purpose": purpose,
                        "line_count": line_count,
                        "issue_count": issue_count
                    }
                ))
            
            # Sort by priority descending
            file_contexts.sort(key=lambda fc: fc.priority_score, reverse=True)
            
            return file_contexts
            
        except Exception as e:
            print(f"⚠️  Error loading files: {e}")
            return []
    
    def _calculate_priority(
        self, 
        file_path: str, 
        last_modified: str, 
        issue_count: int,
        size_bytes: int
    ) -> float:
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
        except:
            pass
        
        # Has issues (+30 per issue, max 60)
        score += min(issue_count * 30, 60)
        
        # Small files preferred (+20 if < 5KB)
        if size_bytes < 5000:
            score += 20
        
        # Core files (+25)
        core_indicators = ['main', 'config', 'init', '__init__', 'app', 'index']
        if any(ind in file_path.lower() for ind in core_indicators):
            score += 25
        
        # Python files (+5)
        if file_path.endswith('.py'):
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
    
    def _get_prioritized_suggestions(self, task_id: str) -> Optional[str]:
        """Get prioritized suggestions from prioritizer"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, content
                    FROM messages
                    WHERE task_id = ? AND from_agent = 'prioritizer'
                    AND to_agent = 'orchestrator' AND read = 0
                    ORDER BY timestamp DESC LIMIT 1
                """, (task_id,))
                
                result = cursor.fetchone()
                if result:
                    msg_id, content = result
                    cursor.execute("UPDATE messages SET read = 1 WHERE id = ?", (msg_id,))
                    return content
                
            return None
        except:
            return None


# Global singleton
_context_manager = None

def get_context_manager() -> ContextManager:
    """Get global context manager"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager