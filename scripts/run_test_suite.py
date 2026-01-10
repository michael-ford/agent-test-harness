#!/usr/bin/env python3
"""
Agent Test Harness - Core Test Runner

Executes test suites against Claude Code agents with multi-turn reflection.
Provides cost estimation, timeout handling, and immediate result persistence.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml


# =============================================================================
# Constants
# =============================================================================

SCHEMA_VERSION = "1.0"
MAX_RECURSION_DEPTH = 2
COST_PER_TEST_ESTIMATE = 0.08  # Rough estimate in USD

REFLECTION_PROMPT = """Now that you've completed the task, please reflect on your process:

1. **Process**: What steps did you take to answer this question?
2. **What Worked**: What aspects of the skill, data structure, or instructions helped you succeed?
3. **What Didn't Work**: What was confusing, inefficient, or required workarounds?
4. **Improvements**: How could the skill, data structure, or instructions be improved to make this easier?

Respond in JSON format with keys: process_steps, what_worked, what_didnt_work, improvement_suggestions (all arrays of strings)."""


# =============================================================================
# Utility Functions
# =============================================================================

def strip_markdown_code_fences(text: str) -> str:
    """
    Strip markdown code fences from text.

    Claude often wraps JSON responses in ```json ... ``` code fences.
    This function extracts the content from within the fences.
    """
    if not text:
        return text

    text = text.strip()

    # Check for code fence pattern: ```json or ``` at start
    if text.startswith("```"):
        lines = text.split("\n")

        # Find the opening fence (first line)
        # It might be ```json, ```JSON, or just ```
        if lines[0].startswith("```"):
            # Find the closing fence
            end_idx = len(lines) - 1
            while end_idx > 0 and not lines[end_idx].strip() == "```":
                end_idx -= 1

            # Extract content between fences
            if end_idx > 0:
                content = "\n".join(lines[1:end_idx])
                return content.strip()

    return text


# =============================================================================
# Recursion Protection
# =============================================================================

def check_recursion_depth() -> int:
    """Check and increment recursion depth. Exit if too deep."""
    depth = int(os.environ.get("AGENT_TEST_DEPTH", "0"))
    if depth > MAX_RECURSION_DEPTH:
        sys.exit(f"Error: Maximum test recursion depth ({MAX_RECURSION_DEPTH}) exceeded")
    os.environ["AGENT_TEST_DEPTH"] = str(depth + 1)
    return depth


# =============================================================================
# YAML Loading and Validation
# =============================================================================

def load_test_suite(path: Path) -> dict:
    """Load and parse a test suite YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Test suite file not found: {path}")

    with open(path, 'r') as f:
        suite = yaml.safe_load(f)

    if not suite:
        raise ValueError("Test suite file is empty")

    return suite


def validate_suite(suite: dict) -> list[str]:
    """
    Validate a test suite configuration.
    Returns a list of error messages (empty if valid).
    """
    errors = []

    # Required fields
    if not suite.get("name"):
        errors.append("Missing required field: 'name'")

    if not suite.get("agent_dir"):
        errors.append("Missing required field: 'agent_dir'")
    else:
        agent_dir = Path(suite["agent_dir"])
        if not agent_dir.exists():
            errors.append(f"agent_dir does not exist: {agent_dir}")
        elif not agent_dir.is_dir():
            errors.append(f"agent_dir is not a directory: {agent_dir}")

    if not suite.get("tests"):
        errors.append("Missing required field: 'tests' (must be a non-empty list)")
    else:
        # Validate tests
        test_ids = set()
        for i, test in enumerate(suite["tests"]):
            if not isinstance(test, dict):
                errors.append(f"Test {i} is not a valid object")
                continue

            test_id = test.get("id")
            if not test_id:
                errors.append(f"Test {i} missing required field: 'id'")
            elif test_id in test_ids:
                errors.append(f"Duplicate test id: '{test_id}'")
            else:
                test_ids.add(test_id)

            if not test.get("prompt"):
                errors.append(f"Test '{test_id or i}' missing required field: 'prompt'")

    return errors


# =============================================================================
# User Interaction
# =============================================================================

def prompt_yes_no(message: str, default: bool = False) -> bool:
    """Prompt user for yes/no confirmation."""
    suffix = "[y/N]" if not default else "[Y/n]"
    try:
        response = input(f"{message} {suffix} ").strip().lower()
        if not response:
            return default
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def prompt_timeout() -> Optional[int]:
    """Prompt user for timeout selection. Returns seconds or None."""
    print("\nPer-test timeout:")
    print("  [1] 5 minutes")
    print("  [2] 10 minutes")
    print("  [3] No timeout")

    try:
        choice = input("Select timeout [1]: ").strip()
        if not choice or choice == "1":
            return 300  # 5 minutes
        elif choice == "2":
            return 600  # 10 minutes
        elif choice == "3":
            return None
        else:
            print("Invalid choice, using 5 minutes")
            return 300
    except (EOFError, KeyboardInterrupt):
        print("\nUsing default timeout (5 minutes)")
        return 300


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def format_cost(cost: float) -> str:
    """Format cost in USD."""
    return f"${cost:.2f}"


# =============================================================================
# Results Management
# =============================================================================

def get_results_dir(suite_name: str, agent_dir: Path) -> Path:
    """Get the results directory for a test run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = agent_dir / ".agent-test-results" / suite_name / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def write_test_result(results_dir: Path, test_id: str, result: dict) -> Path:
    """Write a single test result to disk immediately."""
    result_path = results_dir / f"{test_id}.json"
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)
    return result_path


# =============================================================================
# Claude CLI Execution
# =============================================================================

def run_claude_command(
    prompt: str,
    agent_dir: Path,
    allowed_tools: Optional[str] = None,
    permission_mode: Optional[str] = None,
    max_turns: int = 10,
    session_id: Optional[str] = None,
    timeout: Optional[int] = None,
) -> dict:
    """
    Execute a claude command and return parsed results.

    Returns dict with:
        - success: bool
        - result: str (response text)
        - session_id: str (if available)
        - cost_usd: float
        - num_turns: int
        - error: str (if failed)
    """
    # Build command
    cmd = ["claude", "-p", prompt, "--output-format", "json"]

    if session_id:
        cmd.extend(["--resume", session_id])

    if allowed_tools:
        cmd.extend(["--allowedTools", allowed_tools])

    if permission_mode:
        cmd.extend(["--permission-mode", permission_mode])

    cmd.extend(["--max-turns", str(max_turns)])

    try:
        result = subprocess.run(
            cmd,
            cwd=agent_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Parse JSON output
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "result": result.stdout,
                "error": f"Failed to parse JSON output: {result.stderr}",
                "session_id": None,
                "cost_usd": 0.0,
                "num_turns": 0,
            }

        # Extract fields from claude output
        # The claude CLI outputs JSON with these fields:
        # - result: the text response (may be absent for error_max_turns)
        # - session_id: session identifier
        # - total_cost_usd: total API cost
        # - num_turns: number of conversation turns
        # - subtype: "success" or "error_max_turns"
        subtype = output.get("subtype", "success")
        response_text = output.get("result", output.get("message", ""))
        session = output.get("session_id", output.get("sessionId"))
        # CLI uses total_cost_usd, not cost_usd
        cost = output.get("total_cost_usd", output.get("cost_usd", output.get("costUsd", 0.0)))
        num_turns = output.get("num_turns", output.get("numTurns", 1))

        # Handle case where response_text might be a dict
        if isinstance(response_text, dict):
            response_text = json.dumps(response_text)

        # Handle error_max_turns - this means the task didn't complete within max turns
        # The CLI still returns exit code 0 but with no result text
        error_msg = None
        if subtype == "error_max_turns":
            error_msg = f"Task did not complete within {num_turns} turns (max_turns limit reached)"
            if not response_text:
                response_text = "[Task incomplete - max turns reached]"
        elif result.returncode != 0:
            error_msg = result.stderr

        return {
            "success": result.returncode == 0 and subtype == "success",
            "result": response_text,
            "session_id": session,
            "cost_usd": float(cost) if cost else 0.0,
            "num_turns": int(num_turns) if num_turns else 1,
            "error": error_msg,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "result": "",
            "error": f"Test timed out after {timeout} seconds",
            "session_id": None,
            "cost_usd": 0.0,
            "num_turns": 0,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "result": "",
            "error": "claude CLI not found. Is it installed and in PATH?",
            "session_id": None,
            "cost_usd": 0.0,
            "num_turns": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "result": "",
            "error": str(e),
            "session_id": None,
            "cost_usd": 0.0,
            "num_turns": 0,
        }


# =============================================================================
# Test Execution
# =============================================================================

def run_single_test(
    test: dict,
    suite: dict,
    timeout: Optional[int],
) -> dict:
    """
    Run a single test with reflection turn.

    Returns complete result dict ready for JSON serialization.
    """
    test_id = test["id"]
    prompt = test["prompt"]
    agent_dir = Path(suite["agent_dir"])

    start_time = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Initialize result structure
    result = {
        "schema_version": SCHEMA_VERSION,
        "test_id": test_id,
        "success": False,
        "turn1": None,
        "turn2_reflection": None,
        "total_cost_usd": 0.0,
        "duration_seconds": 0.0,
        "timestamp": timestamp,
    }

    # Turn 1: Execute test prompt
    turn1 = run_claude_command(
        prompt=prompt,
        agent_dir=agent_dir,
        allowed_tools=suite.get("allowed_tools"),
        permission_mode=suite.get("permission_mode"),
        max_turns=suite.get("max_turns", 10),
        timeout=timeout,
    )

    result["turn1"] = {
        "result": turn1["result"],
        "session_id": turn1["session_id"],
        "cost_usd": turn1["cost_usd"],
        "num_turns": turn1["num_turns"],
    }

    if turn1.get("error"):
        result["turn1"]["error"] = turn1["error"]

    total_cost = turn1["cost_usd"]

    # Validate session_id exists for Turn 2
    if not turn1["session_id"]:
        result["success"] = False
        result["turn1"]["error"] = result["turn1"].get("error", "") + " No session_id returned from Turn 1."
    else:
        # Turn 2: Reflection
        turn2 = run_claude_command(
            prompt=REFLECTION_PROMPT,
            agent_dir=agent_dir,
            session_id=turn1["session_id"],
            max_turns=2,
            timeout=timeout,
        )

        result["turn2_reflection"] = {
            "result": turn2["result"],
            "cost_usd": turn2["cost_usd"],
        }

        if turn2.get("error"):
            result["turn2_reflection"]["error"] = turn2["error"]

        total_cost += turn2["cost_usd"]

        # Test is successful if Turn 1 succeeded (Turn 2 is informational)
        result["success"] = turn1["success"]

    # Finalize result
    end_time = time.time()
    result["total_cost_usd"] = total_cost
    result["duration_seconds"] = round(end_time - start_time, 2)

    return result


def run_test_suite(suite: dict, timeout: Optional[int], results_dir: Path) -> list[dict]:
    """Run all tests in a suite, writing results immediately."""
    tests = suite["tests"]
    total_tests = len(tests)
    results = []

    passed = 0
    total_cost = 0.0
    start_time = time.time()

    print(f"\nRunning {total_tests} tests...\n")

    for i, test in enumerate(tests, 1):
        test_id = test["id"]
        test_start = time.time()

        # Show progress
        print(f"[{i}/{total_tests}] {test_id} ", end="", flush=True)

        # Run the test
        result = run_single_test(test, suite, timeout)
        results.append(result)

        # Write immediately
        write_test_result(results_dir, test_id, result)

        # Update counters
        if result["success"]:
            passed += 1
        total_cost += result["total_cost_usd"]

        # Show result
        dots = "." * max(1, 50 - len(test_id))
        status = "PASS" if result["success"] else "FAIL"
        duration = format_duration(result["duration_seconds"])
        cost = format_cost(result["total_cost_usd"])
        print(f"{dots} {status} ({cost}, {duration})")

    # Summary
    total_duration = time.time() - start_time
    print(f"\n{'=' * 60}")
    status_symbol = "✓" if passed == total_tests else "✗"
    print(f"{status_symbol} {passed}/{total_tests} passed | Total: {format_cost(total_cost)} | Duration: {format_duration(total_duration)}")
    print(f"Results saved to: {results_dir}")

    return results


# =============================================================================
# Aggregation
# =============================================================================

def aggregate_results(results: list[dict], results_dir: Path) -> dict:
    """
    Aggregate test results and extract improvement suggestions.

    This function provides inline aggregation for immediate feedback,
    then calls the standalone aggregate_results.py script to generate
    the full aggregate-summary.json and aggregate-report.md files.
    """
    aggregation = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_tests": len(results),
            "passed": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "total_cost_usd": sum(r["total_cost_usd"] for r in results),
            "total_duration_seconds": sum(r["duration_seconds"] for r in results),
        },
        "failed_tests": [],
        "improvement_suggestions": [],
        "what_worked": [],
        "what_didnt_work": [],
    }

    # Collect data from reflections
    for result in results:
        if not result["success"]:
            aggregation["failed_tests"].append({
                "test_id": result["test_id"],
                "error": result.get("turn1", {}).get("error", "Unknown error"),
            })

        # Parse reflection if available
        reflection = result.get("turn2_reflection", {})
        reflection_text = reflection.get("result", "")

        if reflection_text:
            try:
                # Strip markdown code fences before parsing JSON
                clean_text = strip_markdown_code_fences(reflection_text)
                # Try to parse as JSON
                reflection_data = json.loads(clean_text)

                if isinstance(reflection_data, dict):
                    # Extract arrays
                    if "improvement_suggestions" in reflection_data:
                        for suggestion in reflection_data["improvement_suggestions"]:
                            if suggestion not in aggregation["improvement_suggestions"]:
                                aggregation["improvement_suggestions"].append(suggestion)

                    if "what_worked" in reflection_data:
                        for item in reflection_data["what_worked"]:
                            if item not in aggregation["what_worked"]:
                                aggregation["what_worked"].append(item)

                    if "what_didnt_work" in reflection_data:
                        for item in reflection_data["what_didnt_work"]:
                            if item not in aggregation["what_didnt_work"]:
                                aggregation["what_didnt_work"].append(item)
            except json.JSONDecodeError:
                # Reflection wasn't valid JSON, store raw
                pass

    # Write legacy aggregation file (for backwards compatibility)
    agg_path = results_dir / "_aggregation.json"
    with open(agg_path, 'w') as f:
        json.dump(aggregation, f, indent=2)

    # Also run the standalone aggregation script for full output
    # This generates aggregate-summary.json and aggregate-report.md
    script_dir = Path(__file__).parent
    agg_script = script_dir / "aggregate_results.py"

    if agg_script.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(agg_script), str(results_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"\nWarning: Aggregation script failed: {result.stderr}",
                      file=sys.stderr)
        except Exception as e:
            print(f"\nWarning: Could not run aggregation script: {e}",
                  file=sys.stderr)
    else:
        print(f"\nNote: Standalone aggregation script not found at {agg_script}")

    # Print summary of improvements
    if aggregation["improvement_suggestions"]:
        print(f"\nImprovement Suggestions ({len(aggregation['improvement_suggestions'])}):")
        for suggestion in aggregation["improvement_suggestions"][:5]:
            print(f"  - {suggestion}")
        if len(aggregation["improvement_suggestions"]) > 5:
            print(f"  ... and {len(aggregation['improvement_suggestions']) - 5} more")

    return aggregation


# =============================================================================
# Dry Run
# =============================================================================

def dry_run(suite_path: Path) -> bool:
    """
    Perform dry-run validation of a test suite.
    Returns True if validation passes, False otherwise.
    """
    print(f"Dry run: validating {suite_path}\n")

    # Try to load YAML
    try:
        suite = load_test_suite(suite_path)
        print("  [✓] YAML parses correctly")
    except Exception as e:
        print(f"  [✗] YAML parse error: {e}")
        return False

    # Validate suite
    errors = validate_suite(suite)

    if not errors:
        print("  [✓] Suite configuration is valid")
        print(f"  [✓] agent_dir exists: {suite['agent_dir']}")
        print(f"  [✓] All {len(suite['tests'])} test IDs are unique")
        print("\nValidation passed!")
        return True
    else:
        print("  [✗] Validation errors:")
        for error in errors:
            print(f"      - {error}")
        print("\nValidation failed!")
        return False


# =============================================================================
# Main
# =============================================================================

def main():
    # Check recursion depth first
    depth = check_recursion_depth()
    if depth > 0:
        print(f"[Note: Running at recursion depth {depth}]")

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Run agent test suites with multi-turn reflection"
    )
    parser.add_argument(
        "suite_path",
        type=Path,
        help="Path to the test suite YAML file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the test suite without running tests"
    )

    args = parser.parse_args()

    # Dry run mode
    if args.dry_run:
        success = dry_run(args.suite_path)
        sys.exit(0 if success else 1)

    # Normal run
    # Load and validate suite
    try:
        suite = load_test_suite(args.suite_path)
    except Exception as e:
        print(f"Error loading test suite: {e}")
        sys.exit(1)

    errors = validate_suite(suite)
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    # Show suite info
    print(f"\nTest Suite: {suite['name']}")
    if suite.get("description"):
        print(f"Description: {suite['description']}")
    print(f"Agent directory: {suite['agent_dir']}")
    print(f"Tests to run: {len(suite['tests'])}")

    # Cost estimation
    estimated_cost = len(suite['tests']) * COST_PER_TEST_ESTIMATE
    print(f"\nEstimated cost: ~{format_cost(estimated_cost)} for {len(suite['tests'])} tests")

    if not prompt_yes_no("Continue?"):
        print("Aborted.")
        sys.exit(0)

    # Get timeout preference
    timeout = prompt_timeout()

    # Create results directory
    agent_dir = Path(suite['agent_dir'])
    results_dir = get_results_dir(suite['name'], agent_dir)

    # Run tests
    results = run_test_suite(suite, timeout, results_dir)

    # Aggregate results
    aggregate_results(results, results_dir)

    # Exit with appropriate code
    all_passed = all(r["success"] for r in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
