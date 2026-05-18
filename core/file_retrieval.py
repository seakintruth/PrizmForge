"""Explicit file retrieval - bypass context limits"""
from pathlib import Path
from typing import Optional
from core.file_operations import get_file_content_from_db

def get_file_explicit(file_path: str) -> Optional[str]:
    """
    Retrieve file content directly, bypassing context limits
    
    This allows agents to request specific files when needed,
    regardless of token budget constraints.
    """
    # Try database first (fastest)
    content = get_file_content_from_db(file_path)
    if content:
        return content
    
    # Try filesystem as fallback
    try:
        from core.config import get_config
        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))
        full_path = project_dir / file_path
        
        if full_path.exists() and full_path.is_file():
            return full_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"⚠️  Failed to read {file_path}: {e}")
    
    return None


def format_file_with_path(file_path: str) -> str:
    """
    Get file with formatting, or error message if not found
    """
    content = get_file_explicit(file_path)
    
    if content is None:
        return f"❌ File not found: {file_path}"
    
    # Detect language for syntax highlighting
    ext_to_lang = {
        '.py': 'python', '.js': 'javascript', '.md': 'markdown',
        '.json': 'json', '.yml': 'yaml', '.txt': 'text'
    }
    
    ext = Path(file_path).suffix.lower()
    lang = ext_to_lang.get(ext, '')
    
    return f"```{lang} {file_path}\n{content}\n```"