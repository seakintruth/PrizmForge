import os

def consolidate_project(root_dir, output_filename="project_review.md"):
    # Extensions to include
    valid_extensions = ('.py', '.md', '.json', '.sh')
    
    # Files to ignore (extract just the filename to avoid path mismatch issues)
    output_basename = os.path.basename(output_filename)
    ignored_files = {output_basename, "api_key.json"}
    ignored_dirs = {".git", "__pycache__", "venv", "exports"}
    
    # Ensure the target directory for the output file exists
    os.makedirs(os.path.dirname(os.path.abspath(output_filename)), exist_ok=True)
    
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        outfile.write(f"# Project Review: {os.path.abspath(root_dir)}\n\n")
        
        for root, dirs, files in os.walk(root_dir):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            for file in files:
                if file.endswith(valid_extensions) and file not in ignored_files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, root_dir)
                    
                    # Determine markdown code block language
                    lang = "python" if file.endswith(".py") else "json" if file.endswith(".json") else "markdown"
                    
                    outfile.write(f"## File: {relative_path}\n")
                    outfile.write(f"```{lang}\n")
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"[Error reading file: {e}]")
                    
                    outfile.write(f"\n```\n\n---\n\n")
                    
    print(f"✅ Consolidation complete! Created: {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    # Determine the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Target the project path: ../ relative to this script
    target_project_path = os.path.abspath(os.path.join(script_dir, ".."))
    
    # Define the output report path: ../report/project_review.md
    report_dir = os.path.abspath(os.path.join(script_dir, "..", "report"))
    output_file_path = os.path.join(report_dir, "project_review.md")
    
    consolidate_project(target_project_path, output_filename=output_file_path)