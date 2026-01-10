---
name: agent-testing
description: Test Claude Code agents with automated multi-turn execution and structured reflection feedback. Use when testing agents, validating agent behavior, gathering improvement suggestions, or running test suites.
---

# Agent Testing Skill

Test Claude Code agents with automated multi-turn execution and structured feedback collection.

## When to Use

- Testing agent skills before deployment
- Gathering improvement suggestions from agent self-reflection
- Validating agent behavior across multiple scenarios
- Tracking test costs and performance

## Quick Start

1. Create a test suite YAML file
2. Run tests: `python scripts/run_test_suite.py path/to/suite.yaml`
3. Review results in `.agent-test-results/{suite-name}/{timestamp}/`
4. Use `@test-aggregator` to analyze results and prioritize improvements

## Test Suite Format

```yaml
name: "my-agent-tests"
description: "Tests for my agent"
agent_dir: "/path/to/agent/directory"
max_turns: 10
allowed_tools: "Bash,Read,Glob,Grep"
permission_mode: "acceptEdits"

tests:
  - id: "unique-test-id"
    prompt: "What to ask the agent"
    expected_behavior: "Documentation of expected behavior"
    tags: ["category"]
```

See `references/test-suite-schema.md` for complete field reference.

## Multi-Turn Reflection

Each test runs in two turns:

**Turn 1 - Task Execution:**
The agent receives your test prompt and attempts to complete the task.

**Turn 2 - Reflection:**
The agent reflects on its process, answering:
- What steps did it take?
- What worked well?
- What was confusing or inefficient?
- How could the skill be improved?

This reflection data powers the improvement suggestions in aggregated results.

See `references/reflection-prompt.md` for the exact prompt template.

## Understanding Results

### Individual Test Results

Each test produces a JSON file (`{test-id}.json`) containing:
- `test_id`: Test identifier
- `prompt`: The prompt sent
- `success`: Whether the test completed
- `turn1_response`: Agent's task response
- `turn2_reflection`: Agent's reflection (JSON or prose)
- `cost_usd`: API cost for this test
- `duration_seconds`: Time to complete
- `error`: Error message if failed

### Aggregate Results

After all tests complete, aggregation produces:

**`aggregate-summary.json`:**
- Total/passed/failed counts
- Combined cost and duration
- Collected `what_worked` items
- Collected `what_didnt_work` items
- All `improvement_suggestions`

**`aggregate-report.md`:**
Human-readable summary with statistics and all suggestions.

## CLI Usage

### Run a test suite

```bash
python scripts/run_test_suite.py path/to/suite.yaml
```

### Dry run (validate without executing)

```bash
python scripts/run_test_suite.py path/to/suite.yaml --dry-run
```

## Analyzing Results

After running a test suite, use the test-aggregator agent:

```
@test-aggregator Analyze results in .agent-test-results/my-suite/2026-01-10_143022/
```

The aggregator will:
- Group improvement suggestions into themes
- Prioritize by frequency and impact
- Identify quick wins vs systemic issues
- Analyze any failed tests
- Provide actionable next steps

## Best Practices

1. **Unique test IDs**: Each test must have a unique identifier within the suite
2. **Clear prompts**: Write prompts that clearly specify the task
3. **Document expectations**: Use `expected_behavior` for documentation
4. **Start small**: Run 3-5 tests initially, expand after validating setup
5. **Set appropriate max_turns**: Complex tasks need more turns (10-15)
6. **Review reflections**: The improvement suggestions are the primary value

## File Structure

```
.agent-test-results/
  {suite-name}/
    {timestamp}/
      test-id-1.json
      test-id-2.json
      aggregate-summary.json
      aggregate-report.md
```

## Troubleshooting

**Tests timing out:**
Increase `max_turns` in suite config or simplify the test prompt.

**Empty reflections:**
The agent may have hit max turns before reflection. Increase `max_turns`.

**Permission errors:**
Ensure `allowed_tools` includes tools the agent needs. Use `permission_mode: "acceptEdits"`.

**Missing results:**
Check that `agent_dir` exists and is accessible.
