# Test Suite YAML Schema

Complete reference for test suite configuration files.

## Complete Format

```yaml
# Required fields
name: "suite-name"                    # Unique identifier for the suite
agent_dir: "/path/to/agent"           # Directory where the agent runs

# Optional fields (with defaults)
description: "Suite description"      # Human-readable description
max_turns: 10                         # Max turns per test (default: 10)
allowed_tools: "Bash,Read,Glob,Grep"  # Tools to auto-approve (default: all)
permission_mode: "acceptEdits"        # Permission mode (default: acceptEdits)

# Test cases
tests:
  - id: "unique-test-id"              # Must be unique within suite
    prompt: "The prompt to send"      # Required: what to ask the agent
    expected_behavior: "Description"  # Optional: for documentation
    tags: ["tag1", "tag2"]            # Optional: for categorization
```

## Field Reference

### name (required)

Unique identifier used in results directory path. Use kebab-case.

```yaml
name: "pm-assistant-airtable-tests"
```

### agent_dir (required)

Absolute path to the directory where the tested agent should run. This directory should contain `.claude/` or `CLAUDE.md` for the agent's context.

```yaml
agent_dir: "/Users/mikeford/ola-agents/pm-assistant"
```

### description

Human-readable description of what the test suite validates.

```yaml
description: "Tests for Airtable snapshot navigator skill"
```

### max_turns

Maximum number of agentic turns allowed per test. Lower values complete faster but may not allow complex tasks. Default: 10.

```yaml
max_turns: 15  # For complex multi-step tasks
max_turns: 5   # For simple queries
```

### allowed_tools

Comma-separated list of tools to auto-approve. Common configurations:

```yaml
# Read-only file operations
allowed_tools: "Bash,Read,Glob,Grep"

# With write access
allowed_tools: "Bash,Read,Write,Edit,Glob,Grep"

# All tools (omit or leave empty)
allowed_tools: ""
```

### permission_mode

How Claude handles permissions:

- `acceptEdits` - Auto-accept file edits (recommended for testing)
- `plan` - Plan mode only (no actual edits)
- `default` - Standard permission prompts

```yaml
permission_mode: "acceptEdits"
```

### tests (required)

Array of test case objects.

### tests[].id (required)

Unique identifier for the test. Used in output filenames. Use kebab-case.

```yaml
- id: "query-overdue-tasks"
```

### tests[].prompt (required)

The prompt to send to the agent. Can be multi-line using YAML literal block:

```yaml
- id: "complex-query"
  prompt: |
    Find all tasks that meet these criteria:
    1. Assigned to michael@olastrategy.com
    2. Due before end of this week
    3. Not yet completed

    Format results as a markdown table.
```

### tests[].expected_behavior

Description of expected behavior. Documentation only - not validated automatically. Useful for test maintenance and result review.

```yaml
expected_behavior: "Should query tasks table, filter by owner and due_date, exclude completed status"
```

### tests[].tags

Array of tags for categorization. Reserved for future filtering support.

```yaml
tags: ["date-filter", "status-filter", "complex"]
```

## Full Example

```yaml
name: "pm-assistant-airtable"
description: "Tests for Airtable snapshot navigator skill"
agent_dir: "/Users/mikeford/ola-agents/pm-assistant"
max_turns: 10
allowed_tools: "Bash,Read,Glob,Grep"
permission_mode: "acceptEdits"

tests:
  - id: "query-my-tasks"
    prompt: "What tasks are assigned to michael@olastrategy.com?"
    expected_behavior: "Should query tasks table and filter by owner email"
    tags: ["basic", "owner-query"]

  - id: "query-overdue"
    prompt: "What tasks are overdue?"
    expected_behavior: "Should filter by due_date < today and status != complete"
    tags: ["date-filter", "status-filter"]

  - id: "count-by-status"
    prompt: "How many tasks are in each status?"
    expected_behavior: "Should GROUP BY status and COUNT"
    tags: ["aggregation"]

  - id: "find-high-priority"
    prompt: |
      Find all high-priority tasks that are:
      - Not completed
      - Due within the next 7 days

      List them sorted by due date.
    expected_behavior: "Should combine priority, status, and date filters with ORDER BY"
    tags: ["complex", "priority", "date-filter"]
```

## Validation

Run `--dry-run` to validate your suite before executing:

```bash
python scripts/run_test_suite.py path/to/suite.yaml --dry-run
```

This checks:
- YAML syntax is valid
- Required fields are present
- `agent_dir` exists
- All test IDs are unique within the suite

## Common Mistakes

**Duplicate test IDs:**
Each test must have a unique `id`. The dry-run will catch duplicates.

**Relative agent_dir:**
Use absolute paths for `agent_dir`.

**Overly complex prompts:**
Break complex scenarios into multiple simpler tests for better isolation.

**Too few max_turns:**
If tests timeout, increase `max_turns`. The reflection turn counts toward the limit.
