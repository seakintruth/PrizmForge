"""CLI operating modes and state management"""
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

class CLIMode(Enum):
    """CLI operating modes"""
    SEMI_ATTENDED = "semi_attended"  # Wait for human input between tasks
    UNATTENDED = "unattended"        # Run continuously for X hours

@dataclass
class UnattendedConfig:
    """Configuration for unattended mode"""
    max_duration_hours: float = 8.0
    auto_continue: bool = True
    checkpoint_interval_minutes: int = 30
    max_iterations_per_task: int = 20
    min_idle_minutes: float = 5.0
    auto_generate_tasks: bool = True
    prioritize_critical_issues: bool = True
    
    @classmethod
    def from_config(cls, config: dict) -> 'UnattendedConfig':
        """Load from config dictionary"""
        cli_config = config.get("cli_mode", {})
        unattended = cli_config.get("unattended", {})
        
        return cls(
            max_duration_hours=unattended.get("max_duration_hours", 8.0),
            auto_continue=unattended.get("auto_continue", True),
            checkpoint_interval_minutes=unattended.get("checkpoint_interval_minutes", 30),
            max_iterations_per_task=unattended.get("max_iterations_per_task", 20),
            min_idle_minutes=unattended.get("min_idle_minutes", 5.0),
            auto_generate_tasks=unattended.get("auto_generate_tasks", True),
            prioritize_critical_issues=unattended.get("prioritize_critical_issues", True)
        )
    
    def get_end_time(self, start_time: datetime = None) -> datetime:
        """Get end time for unattended run"""
        if start_time is None:
            start_time = datetime.now()
        return start_time + timedelta(hours=self.max_duration_hours)

@dataclass
class CLIState:
    """Track CLI state across modes"""
    mode: CLIMode
    start_time: datetime
    task_counter: int = 1
    total_files_modified: int = 0
    total_iterations: int = 0
    current_task_id: Optional[str] = None
    last_checkpoint: Optional[datetime] = None
    
    def should_checkpoint(self, interval_minutes: int) -> bool:
        """Check if we should save checkpoint"""
        if self.last_checkpoint is None:
            return True
        elapsed = (datetime.now() - self.last_checkpoint).total_seconds() / 60
        return elapsed >= interval_minutes
    
    def update_checkpoint(self):
        """Mark checkpoint saved"""
        self.last_checkpoint = datetime.now()
    
    def elapsed_hours(self) -> float:
        """Get elapsed time in hours"""
        return (datetime.now() - self.start_time).total_seconds() / 3600
    
    def elapsed_minutes(self) -> float:
        """Get elapsed time in minutes"""
        return (datetime.now() - self.start_time).total_seconds() / 60

def get_cli_mode_from_config(config: dict) -> CLIMode:
    """Extract CLI mode from config"""
    cli_config = config.get("cli_mode", {})
    mode_str = cli_config.get("mode", "semi_attended")
    
    try:
        return CLIMode(mode_str)
    except ValueError:
        print(f"⚠️  Invalid CLI mode '{mode_str}', defaulting to semi_attended")
        return CLIMode.SEMI_ATTENDED