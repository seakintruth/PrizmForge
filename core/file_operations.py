"""File operations with database sync"""
import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Set, Any
from datetime import datetime
import json
from core.token_estimator import estimate_tokens
from core.db_connection import get_db_connection

# Known binary extensions (for fast rejection)
_BINARY_EXTENSIONS: Set[str] = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.tiff', '.tif',
    # Archives & compressed
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.jar', '.war',
    # Compiled / Binary
    '.exe', '.dll', '.so', '.dylib', '.bin', '.dat', '.db', '.sqlite',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    # Media
    '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.wav', '.flac',
    # Fonts
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    # Other common binary
    '.pyc', '.pyo', '.class', '.o', '.obj', '.lib', '.a',
}

# Known text extensions (expanded)
_TEXT_EXTENSIONS: Set[str] = {
    # Programming Languages
    '.py', '.pyi', '.pyx', '.js', '.jsx', '.mjs', '.ts', '.tsx',
    '.java', '.kt', '.kts', '.scala', '.sc', '.c', '.h', '.cpp', '.hpp',
    '.cc', '.cxx', '.cs', '.go', '.rs', '.swift', '.rb', '.php',
    '.pl', '.pm', '.lua', '.r', '.dart', '.ex', '.exs', '.erl', '.hrl',
    '.clj', '.cljs', '.cljc',
    
    # Web / Frontend
    '.html', '.htm', '.xhtml', '.css', '.scss', '.sass', '.less', '.styl',
    '.vue', '.svelte', '.astro',
    
    # Markup / Docs
    '.md', '.markdown', '.mdown', '.mkd', '.rst', '.adoc', '.asciidoc',
    '.tex', '.latex', '.xml', '.xsl', '.xslt', '.svg',
    
    # Config / Data
    '.json', '.json5', '.jsonc', '.yaml', '.yml', '.toml',
    '.ini', '.cfg', '.conf', '.properties', '.env', '.csv', '.tsv',
    '.sql', '.ddl', '.dml',
    
    # Shell / Scripts
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    
    # Other common text
    '.txt', '.text', '.log', '.dockerfile', '.editorconfig',
    '.gitignore', '.gitattributes', '.makefile', '.mk',
}


def is_text_file(file_path: str, sample_size: int = 8192) -> bool:
    """
    Determine whether a file is likely a text file.

    Strategy:
    1. Fast path: Check file extension against known lists.
    2. Fallback: If extension is unknown, inspect file content for binary markers.

    Args:
        file_path: Path to the file.
        sample_size: Number of bytes to read for content inspection.

    Returns:
        True if the file is likely text, False otherwise.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    # === Fast path: Known binary extensions ===
    if suffix in _BINARY_EXTENSIONS:
        return False

    # === Fast path: Known text extensions ===
    if suffix in _TEXT_EXTENSIONS:
        return True

    # === Fallback: Content inspection for unknown extensions ===
    try:
        # Handle files with no extension or unknown extensions
        if not path.exists() or not path.is_file():
            return False

        with open(file_path, 'rb') as f:
            sample = f.read(sample_size)

        # Heuristic: Presence of null byte strongly indicates binary
        if b'\x00' in sample:
            return False

        # Optional: Check ratio of printable characters (more expensive)
        # This helps catch some edge cases
        if len(sample) > 0:
            printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13))
            if printable / len(sample) < 0.7:
                return False

        return True

    except (OSError, IOError, PermissionError):
        # If we can't read the file, be conservative
        return False


def compute_file_hash(content: str) -> str:
    """Compute SHA256 hash"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def get_file_lines_with_guids(file_path: str) -> List[Dict[str, Any]]:
    """
    Retrieve a file's lines with their stable GUIDs from the database.
    Returns a list of {"guid": str, "content": str, "sort_order": float}
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fl.line_guid, fl.content, fl.sort_order
                FROM file_lines fl
                JOIN files f ON f.file_id = fl.file_id
                WHERE f.file_path = ? AND fl.is_deleted = 0
                ORDER BY fl.sort_order
            """, (file_path,))
            
            rows = cursor.fetchall()
        
        return [
            {
                "guid": row[0],
                "content": row[1] or "",
                "sort_order": row[2]
            }
            for row in rows
        ]
    except Exception as e:
        print(f"⚠️  Failed to get lines with GUIDs for {file_path}: {e}")
        return []

def format_file_with_guids(file_path: str) -> str:
    """
    Format file content including line_guids so the Developer can reference them.
    """
    lines = get_file_lines_with_guids(file_path)
    if not lines:
        return f"❌ Could not retrieve file with GUIDs: {file_path}"

    formatted_lines = []
    for line in lines:
        formatted_lines.append(f"[{line['guid']}] {line['content']}")

    return f"```python {file_path}\n" + "\n".join(formatted_lines) + "\n```"

def get_project_directory() -> Path:
    """Get the configured project directory path (always absolute)"""
    from core.config import get_config
    config = get_config()
    project_dir = config.get("project_directory", "./project")
    
    # Path is already normalized in config.py, just convert to Path
    return Path(project_dir)

def should_ignore_file(file_path: str) -> bool:
    """Check if file should be ignored"""
    from core.config import get_config
    config = get_config()
    ignore_patterns = config.get("file_operations", {}).get("ignore_patterns", [])
    
    import fnmatch
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(Path(file_path).name, pattern):
            return True
    return False

def sync_file_to_database(file_path: str, content: str) -> bool:
    """
    Sync file content to database
    COMPUTE TOKEN ESTIMATE HERE (write-time)
    """
    try:
        from core.db import get_db_path
        
        content_hash = compute_file_hash(content)
        file_type = Path(file_path).suffix or "unknown"
        size_bytes = len(content.encode('utf-8'))
        is_binary = 0 if is_text_file(file_path) else 1
        
        # =============Compute tokens once =============
        estimated_tokens = estimate_tokens(content) if not is_binary else 0
        # ====================================================
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO project_files
                (file_path, content, content_hash, last_modified, size_bytes, 
                file_type, indexed_at, is_binary, estimated_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_path, content, content_hash, datetime.now().isoformat(),
                size_bytes, file_type, datetime.now().isoformat(), is_binary,
                estimated_tokens))  # Store pre-computed value
        
        return True
    except Exception as e:
        print(f"  ❌ DB sync error: {e}")
        return False


def get_file_content_from_db(file_path: str) -> Optional[str]:
    """Reconstruct plain file content from database."""
    lines = get_file_lines_with_guids(file_path)
    if not lines:
        return None
    return "\n".join(line["content"] for line in lines)

def format_file_for_agent(file_path: str, include_guids: bool = False) -> str:
    """
    Unified formatter.
    - include_guids=True  → for Developer / Reviewer (governed path)
    - include_guids=False → for background agents (analysis only)
    """
    if include_guids:
        return format_file_with_guids(file_path)
    else:
        # Plain text version (for background agents)
        lines = get_file_lines_with_guids(file_path)
        if not lines:
            return f"# File not found: {file_path}"
        plain_lines = [line["content"] for line in lines]
        return f"```python {file_path}\n" + "\n".join(plain_lines) + "\n```"

def generate_file_summary(file_path: str, content: str) -> Dict:
    """
    Generate file summary
    COMPUTE TOKEN ESTIMATE FOR SUMMARY HERE
    """
    file_type = Path(file_path).suffix
    lines = content.split('\n')
    line_count = len(lines)
    
    summary = {
        "file_path": file_path,
        "line_count": line_count,
        "file_type": file_type,
        "size_bytes": len(content.encode('utf-8'))
    }
    
    # Python-specific analysis
    if file_type == '.py':
        functions = []
        classes = []
        imports = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('def '):
                func_name = line.split('(')[0].replace('def ', '')
                functions.append(func_name)
            elif line.startswith('class '):
                class_name = line.split('(')[0].split(':')[0].replace('class ', '')
                classes.append(class_name)
            elif line.startswith(('import ', 'from ')):
                imports.append(line)
        
        summary["functions"] = functions[:10]
        summary["classes"] = classes[:10]
        summary["imports"] = imports[:10]
        summary["purpose"] = f"Python module with {len(functions)} functions, {len(classes)} classes"
    
    elif file_type in ['.json', '.yml', '.yaml', '.toml']:
        summary["purpose"] = f"Configuration file ({file_type})"
    
    elif file_type in ['.md', '.txt']:
        for line in lines:
            if line.strip():
                summary["purpose"] = f"Documentation: {line.strip()[:50]}"
                break
    
    else:
        summary["purpose"] = f"{file_type} file"
    
    return summary


def save_file_summary(file_path: str, summary: Dict):
    """
    Save file summary to database
    COMPUTE TOKEN ESTIMATE FOR SUMMARY TEXT HERE
    """
    try:
        from core.db import get_db_path
        
        # Build summary text
        summary_text = json.dumps(summary)
        
        # =============Compute tokens for summary =============
        summary_tokens = estimate_tokens(summary_text)
        # ===========================================================
        
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO file_summaries
                (file_path, summary, key_functions, dependencies, purpose, 
                line_count, generated_at, estimated_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                summary_text,
                json.dumps(summary.get("functions", [])),
                json.dumps(summary.get("imports", [])),
                summary.get("purpose", ""),
                summary.get("line_count", 0),
                datetime.now().isoformat(),
                summary_tokens  # Store pre-computed value
            ))
    except Exception as e:
        print(f"  ⚠️  Failed to save summary: {e}")
        
def post_file_metadata_to_bus(file_path: str, operation: str, summary: Dict, task_id: str):
    """Post file metadata to message bus"""
    try:
        from core.db import get_db_path
        from core.db_helpers import post_message
        
        metadata = {
            "file_path": file_path,
            "operation": operation,
            "summary": summary.get("purpose", ""),
            "line_count": summary.get("line_count", 0),
            "functions": summary.get("functions", []),
            "classes": summary.get("classes", [])
        }

        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO file_metadata_bus
                (file_path, operation, metadata, summary, task_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                file_path, operation, json.dumps(metadata),
                summary.get("purpose", ""), task_id, datetime.now().isoformat()
            ))
        
        # Also post to orchestrator
        msg = f"📁 {operation.upper()}: {file_path}\n{summary.get('purpose', '')}\n{summary.get('line_count', 0)} lines"
        post_message("file_manager", "orchestrator", msg, task_id, "MEDIUM")
    except:
        pass