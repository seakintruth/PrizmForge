from pathlib import Path


def get_safe_file_content(file_path: str, project_dir: str):
    """
    Retrieves the content of a file within the project directory while preventing path traversal attacks.

    Ref: Feedback #529 - Ensure the resolved path remains within the base project directory.
    """
    project_dir_path = Path(project_dir).resolve()
    full_path = (project_dir_path / file_path).resolve()

    # Security fix for Feedback #529: Check if the resolved full path stays within the base project directory
    if not full_path.is_relative_to(project_dir_path):
        raise PermissionError(f"Security Error: Path traversal attack detected. Access to {file_path} is denied.")

    return full_path.read_text(encoding="utf-8")
