# Reflection Prompt Template

This prompt is sent as Turn 2 after the test prompt completes. It asks the tested agent to reflect on its process.

## The Prompt

```
Now that you've completed the task, please reflect on your process:

1. **Process**: What steps did you take to answer this question?
2. **What Worked**: What aspects of the skill, data structure, or instructions helped you succeed?
3. **What Didn't Work**: What was confusing, inefficient, or required workarounds?
4. **Improvements**: How could the skill, data structure, or instructions be improved to make this easier?

Respond in JSON format with keys: process_steps, what_worked, what_didnt_work, improvement_suggestions (all arrays of strings).
```

## Expected Response Format

When the agent follows the JSON format instruction:

```json
{
  "process_steps": [
    "Read the SKILL.md to understand available tools",
    "Queried the database using DuckDB",
    "Filtered results by owner email"
  ],
  "what_worked": [
    "Clear schema documentation in the skill",
    "Example queries in references/"
  ],
  "what_didnt_work": [
    "Date comparison syntax wasn't clear",
    "Had to guess at JOIN syntax"
  ],
  "improvement_suggestions": [
    "Add date filtering examples to skill documentation",
    "Include a DuckDB quick reference"
  ]
}
```

## How Results Are Used

The aggregation script extracts these arrays and combines them across all tests:

- `what_worked` items are collected to identify strengths
- `what_didnt_work` items reveal pain points
- `improvement_suggestions` drive skill improvements

## Handling Prose Responses

If the agent responds in prose instead of JSON, the test harness captures the raw text. The test-aggregator agent can still extract key points from prose reflections.

Example prose response:
```
I first read the SKILL.md file to understand what tools were available.
The schema documentation was really helpful. However, I struggled with
date comparisons - the syntax wasn't clear. Adding date filtering examples
would improve the skill.
```

The aggregator can parse this into themes even without structured JSON.

## Customizing the Reflection

The reflection prompt is defined in `scripts/run_test_suite.py`. To customize:

1. Locate the `REFLECTION_PROMPT` constant
2. Modify the questions or format instructions
3. Update the aggregation script if changing JSON keys

Keep the JSON format request - structured data aggregates more reliably than prose.

## Why Reflection Matters

Reflection turns passive testing into active improvement:

- Agents identify gaps that humans might miss
- Suggestions come from actual task execution context
- Patterns across tests reveal systemic issues
- Specific examples make improvements actionable

The two-turn structure ensures the agent completes the task before reflecting, providing authentic feedback on the experience.
