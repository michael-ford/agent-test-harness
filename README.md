# Agent Test Harness

Testing infrastructure for Claude Code agents with multi-turn reflection and LLM-synthesized improvement suggestions.

## Overview

The Agent Test Harness provides automated testing for Claude Code agents. It executes test prompts against your agents, captures their responses, and then uses a reflection turn to gather insights about what worked well and what could be improved.

Key features:
- Multi-turn testing with automatic reflection
- Cost tracking and estimation
- Timeout protection
- Dry-run validation mode
- Immediate result persistence
- Aggregated improvement suggestions

## Installation

1. Clone or download this repository
2. Symlink to your Claude Code plugins directory:

```bash
ln -s /path/to/agent-test-harness ~/.claude/plugins/agent-test-harness
```

3. Install Python dependencies:

```bash
pip install -r scripts/requirements.txt
```

## Usage

### Running Tests

Run tests using the Python script:

```bash
# Normal run
python scripts/run_test_suite.py path/to/suite.yaml

# Dry run (validation only, no API calls)
python scripts/run_test_suite.py path/to/suite.yaml --dry-run
```

The harness will:
1. Validate the test suite YAML
2. Estimate cost and ask for confirmation
3. Ask for timeout preference
4. Execute each test with progress display
5. Run a reflection turn after each test
6. Aggregate results and improvement suggestions

### Test Results

Results are written immediately to:
```
.agent-test-results/{suite_name}/{timestamp}/{test_id}.json
```

## Test Suite YAML Format

Create a YAML file defining your test suite:

```yaml
name: "my-agent-tests"
description: "Tests for my custom agent"
agent_dir: "/path/to/agent/directory"
max_turns: 10
allowed_tools: "Bash,Read,Glob,Grep"
permission_mode: "acceptEdits"

tests:
  - id: "basic-query"
    prompt: "What files are in this directory?"
    expected_behavior: "Agent should list files using ls or Glob"
    tags: ["filesystem", "basic"]

  - id: "code-search"
    prompt: "Find all Python files that import requests"
    expected_behavior: "Agent should use Grep to search for import statements"
    tags: ["search", "python"]
```

### Suite Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier for the suite |
| `description` | No | Human-readable description |
| `agent_dir` | Yes | Working directory for the agent |
| `max_turns` | No | Maximum turns per test (default: 10) |
| `allowed_tools` | No | Comma-separated list of allowed tools |
| `permission_mode` | No | Permission mode: `default`, `acceptEdits`, `bypassPermissions` |

### Test Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique test identifier |
| `prompt` | Yes | The prompt to send to the agent |
| `expected_behavior` | No | Documentation of expected behavior (not validated) |
| `tags` | No | Tags for filtering and organization |

## Output Format

Each test produces a JSON result file:

```json
{
  "schema_version": "1.0",
  "test_id": "basic-query",
  "success": true,
  "turn1": {
    "result": "Agent's response text",
    "session_id": "abc123",
    "cost_usd": 0.05,
    "num_turns": 3
  },
  "turn2_reflection": {
    "result": "Reflection response",
    "cost_usd": 0.03
  },
  "total_cost_usd": 0.08,
  "duration_seconds": 45,
  "timestamp": "2026-01-10T15:30:00Z"
}
```

## Safety Features

### Recursion Protection

The harness includes depth tracking to prevent infinite recursion if a test somehow triggers another test run. Maximum depth is 2.

### Timeout Handling

Before running tests, you'll be prompted to select a timeout:
- 5 minutes (recommended for quick tests)
- 10 minutes (for complex operations)
- No timeout (use with caution)

### Dry Run Mode

Use `--dry-run` to validate your test suite without making any API calls:
- Validates YAML syntax
- Checks that `agent_dir` exists
- Ensures all test IDs are unique
- Reports any validation errors

## Cost Estimation

Before running tests, the harness estimates the total cost based on:
- Number of tests
- Expected turns per test
- Reflection overhead

You'll be asked to confirm before proceeding.

## License

MIT License - see [LICENSE](LICENSE) for details.
