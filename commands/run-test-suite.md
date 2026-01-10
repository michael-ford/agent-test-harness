---
name: run-test-suite
description: Run a test suite against a Claude Code agent. Executes tests with multi-turn reflection and generates aggregate improvement suggestions.
arguments:
  - name: suite_path
    description: Path to the YAML test suite file
    required: true
---

# Run Test Suite

Execute a test suite against a Claude Code agent using the agent-test-harness.

## Process

1. Validate the test suite file exists at the provided path
2. Check if Python dependencies are installed:
   ```bash
   pip show pyyaml > /dev/null 2>&1 || pip install -r ${CLAUDE_PLUGIN_ROOT}/scripts/requirements.txt
   ```
3. First, run in dry-run mode to validate:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/run_test_suite.py "{{ suite_path }}" --dry-run
   ```
4. Run the test harness:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/run_test_suite.py "{{ suite_path }}"
   ```
   Note: The script will interactively prompt the user for:
   - Timeout preference (5 min, 10 min, or no timeout)
   - Cost confirmation based on estimated token usage
5. Monitor progress output for each test
6. After completion, results are in `.agent-test-results/{suite_name}/{timestamp}/`
7. Summarize the results to the user
8. Offer to invoke the test-aggregator agent for LLM synthesis of improvement themes

## Output Location

Results are saved to `.agent-test-results/{suite_name}/{timestamp}/` in the current working directory.

## Example Usage

```
/run-test-suite examples/pm-assistant-airtable.yaml
```

## Next Steps

After tests complete, you can:
- Review individual test results in `.agent-test-results/{suite_name}/{timestamp}/*.json`
- Use the test-aggregator agent for LLM synthesis of improvement themes
