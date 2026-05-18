## Updated Developer Prompt Guidance (Schema-Aware)

Add the following section to your **Developer agent system prompt**:

```markdown
## Governed File Editing – Mandatory Rules

You **must** output all file modifications using the structured `EditPayload` format.  
Raw diffs, full file rewrites, or direct file writes are **not allowed**.

### Required Output Structure

```json
{
  "target_file_path": "relative/path/to/file.py",
  "operations": [ ... ],
  "rationale": "Clear explanation of why this change is needed."
}
```

### Important Schema & Field Requirements

- `target_file_path` is **required** and must be relative to the project root.
- Use the exact operation field names below:

| Operation Type       | Required Fields                                      | Notes |
|----------------------|------------------------------------------------------|-------|
| `replace_block`      | `target_line_guids`, `new_content`                   | GUIDs of lines being replaced |
| `insert_after`       | `after_line_guid`, `new_content`                     | Insert after this GUID, GUID can be null, will append lines |
| `delete_lines`       | `target_line_guids`                                  | GUIDs of lines to delete |
| `update_documentation` | `new_content`                                      | Updates per-file documentation |
| `create_file`        | `target_file_path`, `initial_content` (optional)     | Creates new file |

- Always provide a clear `rationale` at both the operation level and top level.
- The system will automatically capture `affected_line_guids` and `expected_hashes` for optimistic concurrency validation.
- After you output the `EditPayload`, a governed proposal will be created and must pass review before any changes are written to disk.

**Example (replace_block):**
```json
{
  "target_file_path": "core/utils.py",
  "operations": [{
    "type": "replace_block",
    "target_line_guids": ["guid-abc123", "guid-def456"],
    "new_content": ["def improved_function():", "    return True"],
    "rationale": "Improved error handling and clarity"
  }],
  "rationale": "Fixing fragile logic in utility module as requested."
}
```

Failure to follow this format will result in the proposal being rejected.
```

---

### Summary

| Item                        | Status     | Notes |
|----------------------------|------------|-------|
| Schema with `reviewed_at`   | ✅ Updated | Added to `CREATE TABLE` + migration SQL |
| `proposal_builder.py`       | ✅ Updated | v1.6 now correctly sets `reviewed_at` |
| Developer Prompt Guidance   | ✅ Updated | Includes correct field names and schema requirements |

Everything is now consistent with your current `edit_proposals` schema.

Would you like me to proceed with **Sprint 9** (Testing, Hardening & Documentation)?