"""Prioritizer worker - intelligent multi-phase feedback processing"""
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from agents.base import call_agent
from core.db_helpers import post_message
from core.db_connection import get_db_connection
from core.json_parser import parse_json_response
            
@dataclass
class FeedbackItem:
    """Feedback item with metadata"""
    id: int
    from_agent: str
    file_path: str
    priority: str
    category: str
    message: str
    suggestion: str
    timestamp: str
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
    
    def start(self, task_id: str):
        """Start the prioritizer worker"""
        if self.running:
            return
        
        self.running = True
        self.current_task_id = task_id
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="prioritizer-worker"
        )
        self.worker_thread.start()
        print(f"    🎯 Started prioritizer worker (multi-phase intelligent)")
    
    def stop(self):
        """Stop the prioritizer worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        print(f"    🎯 Stopped prioritizer worker")
    
    def _worker_loop(self):
        """Main worker loop - wait for full cycle before starting timer"""
        while self.running:
            try:
                time.sleep(5)  # Check every 5 seconds
                
                if not self.running:
                    break
                
                # Check if we should run a full cycle
                if self._should_run_cycle():
                    print(f"\n    🎯 ━━━ PRIORITIZER CYCLE START ━━━")
                    self._run_full_prioritization_cycle()
                    self.processing_cycle_time = time.time()
                    print(f"    🎯 ━━━ PRIORITIZER CYCLE COMPLETE ━━━\n")
                    self.last_prioritization = time.time()
                
            except Exception as e:
                print(f"    ⚠️  Prioritizer error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(30)
    
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
        
        Phase 1: Categorize uncategorized items
        Phase 2: Score within categories  
        Phase 3: Cross-category ranking
        Phase 4: Post to orchestrator
        """
        # Phase 1: Get all feedback
        all_feedback = self._get_all_feedback()
        
        if not all_feedback:
            print(f"    📊 No feedback to prioritize")
            return
        
        print(f"    📊 Processing {len(all_feedback)} feedback items")
        
        # Phase 2: Categorize uncategorized (batches of 30)
        categorized = self._categorize_feedback(all_feedback)
        
        # Phase 3: Score within categories
        scored_by_category = self._score_within_categories(categorized)
        
        # Phase 4: Cross-category prioritization
        final_ranked = self._cross_category_ranking(scored_by_category)
        
        # Phase 5: Post to orchestrator
        self._post_results(final_ranked)
    
    def _get_all_feedback(self) -> List[FeedbackItem]:
        """Get ALL unaddressed feedback (no limit)"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get ALL unaddressed feedback
                cursor.execute("""
                    SELECT 
                        id, agent_name, file_path, priority, category,
                        message, suggestion, timestamp
                    FROM agent_feedback
                    WHERE task_id = ?
                    AND addressed = 0
                    ORDER BY timestamp DESC
                """, (self.current_task_id,))
                
                feedback_rows = cursor.fetchall()
                
                # Get unread messages
                cursor.execute("""
                    SELECT 
                        id, from_agent, content, priority, timestamp
                    FROM messages
                    WHERE task_id = ?
                    AND to_agent = 'orchestrator'
                    AND read = 0
                    ORDER BY timestamp DESC
                """, (self.current_task_id,))
                
                message_rows = cursor.fetchall()
            
            items = []
            
            # Convert feedback
            for row in feedback_rows:
                # Determine bias based on agent
                bias = 5.0 if row[1] == "human" else 1.0
                
                items.append(FeedbackItem(
                    id=row[0],
                    from_agent=row[1],
                    file_path=row[2],
                    priority=row[3] or "MEDIUM",
                    category=row[4] or "uncategorized",
                    message=row[5],
                    suggestion=row[6] or "",
                    timestamp=row[7],
                    bias_multiplier=bias
                ))
            
            # Convert messages
            for row in message_rows:
                bias = 5.0 if row[1] == "human" else 1.0
                items.append(FeedbackItem(
                    id=row[0],
                    from_agent=row[1],
                    file_path="<message>",
                    priority=row[3] or "MEDIUM",
                    category="message",
                    message=row[2],
                    suggestion="",
                    timestamp=row[4],
                    bias_multiplier=bias
                ))
            
            return items
            
        except Exception as e:
            print(f"    ❌ Error getting feedback: {e}")
            return []
    
    def _categorize_feedback(self, items: List[FeedbackItem]) -> List[FeedbackItem]:
        """Phase 1: Categorize uncategorized items in batches of 30"""
        uncategorized = [item for item in items if item.category == "uncategorized"]
        
        if not uncategorized:
            print(f"    ✓ Phase 1: All items categorized")
            return items
        
        print(f"    → Phase 1: Categorizing {len(uncategorized)} items (batches of 30)")
        
        # Process in batches of 30
        for i in range(0, len(uncategorized), 30):
            batch = uncategorized[i:i+30]
            self._categorize_batch(batch)
        
        print(f"    ✓ Phase 1: Complete")
        return items
    
    def _categorize_batch(self, batch: List[FeedbackItem]):
        """Categorize a batch of items"""
        # Build prompt with message and suggestion context
        prompt = f"Categorize these {len(batch)} feedback items:\n\n"
        
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
    {"id": 1, "category": "security"},
    {"id": 2, "category": "bug"}
  ]
}
"""
        
        try:
            response = call_agent("prioritizer", prompt, self.current_task_id,
                                model_override="gemini-3-flash-preview")
            
            if not response:
                return
            
            # Parse and update categories in database
            # Use centralized parser
            
            data = parse_json_response(
                response,
                expected_keys=["categorized"],
                agent_name="prioritizer/categorize"
            )
            

            if data and "categorized" in data:
                self._update_categories(data["categorized"])
                
        except Exception as e:
            print(f"    ⚠️  Categorization batch error: {e}")
    
    def _update_categories(self, categorized: List[Dict]):
        """Update categories in database"""
        try:
            with get_db_connection() as conn:
                for item in categorized:
                    conn.execute("""
                        UPDATE agent_feedback
                        SET category = ?
                        WHERE id = ?
                    """, (item["category"], item["id"]))
        except Exception as e:
            print(f"    ⚠️  Error updating categories: {e}")
    
    def _score_within_categories(self, items: List[FeedbackItem]) -> Dict[str, List[FeedbackItem]]:
        """Phase 2: Score items within each category"""
        print(f"    → Phase 2: Scoring within categories")
        
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
    
    def _score_category(self, category: str, items: List[FeedbackItem]):
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
    {"id": 1, "score": 85},
    {"id": 2, "score": 60}
  ]
}
"""
        try:
            response = call_agent("prioritizer", prompt, self.current_task_id,
                                model_override="gemini-3-flash-preview")
            
            if not response:
                return

            data = parse_json_response(
                response,
                expected_keys=["scored"],
                agent_name="prioritizer/categorize"
            )

            if data and "scored" in data:
                # Apply scores to items
                score_map = {s["id"]: s["score"] for s in data["scored"]}
                for item in items:
                    if item.id in score_map:
                        item.score = score_map[item.id]
                        
        except Exception as e:
            print(f"    ⚠️  Category scoring error: {e}")
    
    def _cross_category_ranking(self, by_category: Dict[str, List[FeedbackItem]]) -> List[FeedbackItem]:
        """Phase 3: Cross-category prioritization"""
        print(f"    → Phase 3: Cross-category ranking")
        
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
      "id": 123,
      "final_score": 150,
      "rank": 1,
      "action_for_orchestrator": "Fix critical security issue in X"
    }
  ]
}
"""
        
        try:
            response = call_agent("prioritizer", prompt, self.current_task_id,
                                model_override="gemini-3.1-pro-preview")
            
            if not response:
                return all_items[:8]

            data = parse_json_response(
                response,
                expected_keys=["top_suggestions"],
                agent_name="prioritizer/categorize"
            )

            if data and "top_suggestions" in data:
                # Map back to original items
                id_map = {item.id: item for item in all_items}
                ranked = []
                for suggestion in data["top_suggestions"][:8]:
                    item_id = suggestion["id"]
                    if item_id in id_map:
                        item = id_map[item_id]
                        item.score = suggestion.get("final_score", item.score)
                        ranked.append(item)
                
                print(f"    ✓ Phase 3: Ranked top {len(ranked)} items")
                return ranked
            
        except Exception as e:
            print(f"    ⚠️  Cross-category ranking error: {e}")
        
        # Fallback: return top 8 by score
        return sorted(all_items, key=lambda x: x.score, reverse=True)[:8]
    
    def _post_results(self, ranked: List[FeedbackItem]):
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
        post_message(
            "prioritizer", "orchestrator",
            message, self.current_task_id, "HIGH"
        )
        
        # Mark items as read
        self._mark_items_processed(ranked)
        
        print(f"    ✓ Phase 4: Posted to orchestrator")
    
def _mark_items_processed(self, items: List[FeedbackItem]):
    """Mark items as READ (not addressed - that happens when developer fixes them)"""
    try:
        with get_db_connection() as conn:
            for item in items:
                if item.file_path == "<message>":
                    conn.execute("UPDATE messages SET read = 1 WHERE id = ?", (item.id,))
                else:
                    # ✅ GOOD: Only mark messages as read, feedback stays unaddressed
                    # Feedback is marked addressed ONLY when developer actually fixes it
                    pass  # Don't touch agent_feedback.addressed
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