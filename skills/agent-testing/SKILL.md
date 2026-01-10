# Agent Testing Skill

This skill provides guidance on testing Claude Code agents using the agent-test-harness.

## Overview

The agent test harness enables automated testing of Claude Code agents with:
- Multi-turn test execution
- Automatic reflection for improvement insights
- Cost tracking and estimation
- Immediate result persistence

## Quick Start

> **Note:** The `/run-test-suite` slash command will be available in a future release. For now, use the Python script directly.

1. Create a test suite YAML file (see `examples/example-suite.yaml`)
2. Run with `/run-test-suite path/to/suite.yaml`
3. Review results in `.agent-test-results/`

## Test Suite Format

```yaml
name: "suite-name"
description: "Description"
agent_dir: "/path/to/agent/directory"
max_turns: 10
allowed_tools: "Bash,Read,Glob,Grep"

tests:
  - id: "test-id"
    prompt: "Prompt for the agent"
    expected_behavior: "Documentation of expected behavior"
    tags: ["tag1", "tag2"]
```

## Best Practices

1. **Unique test IDs**: Each test must have a unique identifier
2. **Clear prompts**: Write prompts that clearly specify the task
3. **Document expectations**: Use expected_behavior for documentation
4. **Use tags**: Organize tests with meaningful tags
5. **Set appropriate timeouts**: Complex tasks may need longer timeouts

## Understanding Results

Each test produces a JSON file with:
- `turn1`: The agent's response to the test prompt
- `turn2_reflection`: The agent's self-reflection on its process
- Cost and duration metrics

The `_aggregation.json` file summarizes all tests and collects improvement suggestions.
