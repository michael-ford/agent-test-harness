#!/usr/bin/env python3
"""
Agent Test Harness - Results Aggregation Script

Standalone script to aggregate test results from a completed test run.
Can be run after tests complete or re-run later to regenerate aggregation.

Usage:
    python scripts/aggregate_results.py .agent-test-results/suite-name/timestamp/
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# =============================================================================
# Constants
# =============================================================================

SCHEMA_VERSION = "1.0"


# =============================================================================
# Utility Functions
# =============================================================================

def format_duration(seconds: float) -> str:
    """Format duration in human-readable form (e.g., '15m 32s')."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if secs == 0:
        return f"{minutes}m"
    return f"{minutes}m {secs}s"


def format_cost(cost: float) -> str:
    """Format cost in USD."""
    return f"${cost:.2f}"


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely navigate nested dict keys."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result


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
# Result Loading
# =============================================================================

def load_test_results(results_dir: Path) -> list[dict]:
    """
    Load all test result JSON files from a results directory.

    Skips files starting with '_' (like _aggregation.json) and
    handles malformed JSON gracefully.
    """
    results = []

    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    if not results_dir.is_dir():
        raise ValueError(f"Path is not a directory: {results_dir}")

    json_files = sorted(results_dir.glob("*.json"))

    for json_file in json_files:
        # Skip aggregation files (prefixed with _)
        if json_file.name.startswith("_"):
            continue

        # Skip existing aggregate files
        if json_file.name in ("aggregate-summary.json",):
            continue

        try:
            with open(json_file, 'r') as f:
                result = json.load(f)
                results.append(result)
        except json.JSONDecodeError as e:
            print(f"Warning: Skipping malformed JSON file {json_file.name}: {e}",
                  file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error reading {json_file.name}: {e}",
                  file=sys.stderr)

    return results


# =============================================================================
# Reflection Parsing
# =============================================================================

def parse_reflection(reflection: Optional[dict]) -> dict:
    """
    Parse a reflection result, handling both JSON and prose formats.

    Returns dict with:
        - improvement_suggestions: list[str]
        - what_worked: list[str]
        - what_didnt_work: list[str]
        - process_steps: list[str]
    """
    empty_result = {
        "improvement_suggestions": [],
        "what_worked": [],
        "what_didnt_work": [],
        "process_steps": [],
    }

    if not reflection:
        return empty_result

    reflection_text = reflection.get("result", "")

    if not reflection_text:
        return empty_result

    # Strip markdown code fences before parsing JSON
    clean_text = strip_markdown_code_fences(reflection_text)

    # Try to parse as JSON first
    try:
        data = json.loads(clean_text)

        if isinstance(data, dict):
            return {
                "improvement_suggestions": data.get("improvement_suggestions", []),
                "what_worked": data.get("what_worked", []),
                "what_didnt_work": data.get("what_didnt_work", []),
                "process_steps": data.get("process_steps", []),
            }
    except json.JSONDecodeError:
        pass

    # If not valid JSON, treat as prose and return empty
    # (Future enhancement: could parse prose with regex patterns)
    return empty_result


# =============================================================================
# Statistics Calculation
# =============================================================================

def calculate_statistics(results: list[dict]) -> dict:
    """
    Calculate summary statistics from test results.

    Returns dict with all numeric stats.
    """
    if not results:
        return {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "success_rate": 0.0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "avg_turns_per_test": 0.0,
            "avg_cost_per_test": 0.0,
            "avg_duration_per_test": 0.0,
        }

    total_tests = len(results)
    passed = sum(1 for r in results if r.get("success", False))
    failed = total_tests - passed

    total_cost = sum(r.get("total_cost_usd", 0.0) for r in results)
    total_duration = sum(r.get("duration_seconds", 0.0) for r in results)

    # Calculate total turns (sum of turn1 turns)
    total_turns = 0
    for r in results:
        turn1 = r.get("turn1", {})
        total_turns += turn1.get("num_turns", 0) if turn1 else 0

    avg_turns = total_turns / total_tests if total_tests > 0 else 0.0
    avg_cost = total_cost / total_tests if total_tests > 0 else 0.0
    avg_duration = total_duration / total_tests if total_tests > 0 else 0.0
    success_rate = passed / total_tests if total_tests > 0 else 0.0

    return {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "success_rate": round(success_rate, 3),
        "total_cost_usd": round(total_cost, 4),
        "total_duration_seconds": round(total_duration, 2),
        "avg_turns_per_test": round(avg_turns, 1),
        "avg_cost_per_test": round(avg_cost, 4),
        "avg_duration_per_test": round(avg_duration, 2),
    }


# =============================================================================
# Data Aggregation
# =============================================================================

def collect_suggestions(results: list[dict]) -> dict:
    """
    Collect all improvement suggestions, what worked, and what didn't.

    Tracks frequency and deduplicates.

    Returns dict with:
        - improvement_suggestions: list[str] (sorted by frequency)
        - what_worked: list[str]
        - what_didnt_work: list[str]
        - suggestion_counts: dict[str, int] (for debugging)
    """
    suggestion_counter: Counter[str] = Counter()
    worked_set: set[str] = set()
    didnt_work_set: set[str] = set()

    for result in results:
        reflection = result.get("turn2_reflection")
        parsed = parse_reflection(reflection)

        for suggestion in parsed["improvement_suggestions"]:
            if suggestion and isinstance(suggestion, str):
                suggestion_counter[suggestion.strip()] += 1

        for item in parsed["what_worked"]:
            if item and isinstance(item, str):
                worked_set.add(item.strip())

        for item in parsed["what_didnt_work"]:
            if item and isinstance(item, str):
                didnt_work_set.add(item.strip())

    # Sort suggestions by frequency (most common first)
    sorted_suggestions = [
        s for s, _ in suggestion_counter.most_common()
    ]

    return {
        "improvement_suggestions": sorted_suggestions,
        "what_worked": sorted(worked_set),
        "what_didnt_work": sorted(didnt_work_set),
        "suggestion_counts": dict(suggestion_counter),
    }


def collect_failed_tests(results: list[dict]) -> list[dict]:
    """
    Collect information about failed tests.

    Returns list of dicts with test_id and error.
    """
    failed = []

    for result in results:
        if not result.get("success", False):
            test_id = result.get("test_id", "unknown")

            # Try to get error from turn1
            turn1 = result.get("turn1", {})
            error = turn1.get("error") if turn1 else None

            # Fallback to generic message
            if not error:
                error = "Test failed (no specific error message)"

            failed.append({
                "test_id": test_id,
                "error": error,
            })

    return failed


# =============================================================================
# Output Generation
# =============================================================================

def extract_suite_name(results_dir: Path) -> str:
    """Extract suite name from results directory path."""
    # Path format: .agent-test-results/{suite_name}/{timestamp}/
    # So parent.name is timestamp, parent.parent.name is suite_name
    if results_dir.parent.parent.name == ".agent-test-results":
        return results_dir.parent.name
    return results_dir.name


def generate_summary_json(
    results_dir: Path,
    statistics: dict,
    suggestions: dict,
    failed_tests: list[dict],
) -> dict:
    """Generate the aggregate-summary.json structure."""
    suite_name = extract_suite_name(results_dir)

    return {
        "schema_version": SCHEMA_VERSION,
        "suite_name": suite_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results_directory": str(results_dir),
        "statistics": statistics,
        "all_improvement_suggestions": suggestions["improvement_suggestions"],
        "what_worked": suggestions["what_worked"],
        "what_didnt_work": suggestions["what_didnt_work"],
        "failed_tests": failed_tests,
    }


def generate_report_md(
    results_dir: Path,
    statistics: dict,
    suggestions: dict,
    failed_tests: list[dict],
) -> str:
    """Generate the aggregate-report.md markdown content."""
    suite_name = extract_suite_name(results_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    total_duration = format_duration(statistics["total_duration_seconds"])
    total_cost = format_cost(statistics["total_cost_usd"])
    avg_cost = format_cost(statistics["avg_cost_per_test"])
    avg_duration = format_duration(statistics["avg_duration_per_test"])
    success_pct = int(statistics["success_rate"] * 100)

    lines = [
        f"# Test Suite Results: {suite_name}",
        "",
        f"**Run:** {timestamp}",
        f"**Duration:** {total_duration}",
        f"**Cost:** {total_cost}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Tests | {statistics['total_tests']} |",
        f"| Passed | {statistics['passed']} ({success_pct}%) |",
        f"| Failed | {statistics['failed']} |",
        f"| Total Cost | {total_cost} |",
        f"| Total Duration | {total_duration} |",
        f"| Avg Cost/Test | {avg_cost} |",
        f"| Avg Duration/Test | {avg_duration} |",
        f"| Avg Turns/Test | {statistics['avg_turns_per_test']} |",
        "",
    ]

    # Failed tests section
    if failed_tests:
        lines.append("## Failed Tests")
        lines.append("")
        for test in failed_tests:
            lines.append(f"### {test['test_id']}")
            lines.append(f"- **Error:** {test['error']}")
            lines.append("")

    # Improvement suggestions
    if suggestions["improvement_suggestions"]:
        lines.append("## Improvement Suggestions")
        lines.append("")
        lines.append("The following suggestions were collected from agent reflections:")
        lines.append("")
        for i, suggestion in enumerate(suggestions["improvement_suggestions"], 1):
            lines.append(f"{i}. {suggestion}")
        lines.append("")

    # What worked
    if suggestions["what_worked"]:
        lines.append("## What Worked Well")
        lines.append("")
        for item in suggestions["what_worked"]:
            lines.append(f"- {item}")
        lines.append("")

    # What didn't work
    if suggestions["what_didnt_work"]:
        lines.append("## What Didn't Work")
        lines.append("")
        for item in suggestions["what_didnt_work"]:
            lines.append(f"- {item}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Generated by agent-test-harness*")
    lines.append("")

    return "\n".join(lines)


def write_outputs(
    results_dir: Path,
    summary_json: dict,
    report_md: str,
) -> tuple[Path, Path]:
    """Write output files and return their paths."""
    json_path = results_dir / "aggregate-summary.json"
    md_path = results_dir / "aggregate-report.md"

    with open(json_path, 'w') as f:
        json.dump(summary_json, f, indent=2)

    with open(md_path, 'w') as f:
        f.write(report_md)

    return json_path, md_path


# =============================================================================
# Main
# =============================================================================

def aggregate_results(results_dir: Path) -> dict:
    """
    Main aggregation function.

    Loads results, calculates statistics, collects suggestions,
    and writes output files.

    Returns the summary JSON dict.
    """
    # Load results
    print(f"Loading results from: {results_dir}")
    results = load_test_results(results_dir)

    if not results:
        print("Warning: No test results found in directory", file=sys.stderr)
        # Still generate empty outputs

    print(f"Found {len(results)} test result(s)")

    # Calculate statistics
    statistics = calculate_statistics(results)

    # Collect suggestions and feedback
    suggestions = collect_suggestions(results)

    # Collect failed tests
    failed_tests = collect_failed_tests(results)

    # Generate outputs
    summary_json = generate_summary_json(
        results_dir, statistics, suggestions, failed_tests
    )
    report_md = generate_report_md(
        results_dir, statistics, suggestions, failed_tests
    )

    # Write files
    json_path, md_path = write_outputs(results_dir, summary_json, report_md)

    print(f"\nOutput files written:")
    print(f"  - {json_path}")
    print(f"  - {md_path}")

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Summary: {statistics['passed']}/{statistics['total_tests']} passed")
    print(f"Total cost: {format_cost(statistics['total_cost_usd'])}")
    print(f"Total duration: {format_duration(statistics['total_duration_seconds'])}")

    if suggestions["improvement_suggestions"]:
        print(f"\nTop improvement suggestions:")
        for suggestion in suggestions["improvement_suggestions"][:3]:
            print(f"  - {suggestion}")
        remaining = len(suggestions["improvement_suggestions"]) - 3
        if remaining > 0:
            print(f"  ... and {remaining} more")

    return summary_json


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate test results from agent-test-harness runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/aggregate_results.py .agent-test-results/my-suite/20260110_153000/
    python scripts/aggregate_results.py /path/to/results/

Output files are written to the same directory:
    - aggregate-summary.json  (structured data)
    - aggregate-report.md     (human-readable report)
        """
    )
    parser.add_argument(
        "results_dir",
        type=Path,
        help="Path to the test results directory"
    )

    args = parser.parse_args()

    try:
        aggregate_results(args.results_dir)
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
