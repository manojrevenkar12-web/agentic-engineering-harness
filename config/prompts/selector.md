Two engineers each made a change for the same task. You must pick the one to merge. Do not edit any
file.

The candidates are in the files {candidates} in the current directory (unified diffs), with the
results of running the repository's test suite on each below. Read AGENTS.md for what must never
break and what reviewers check, then judge which change does the task correctly with the least risk.
A change that breaks existing tests loses unless both do.

{test_results}

Your final message must be only a JSON object, no prose around it:
{{"choice": <1 or 2>, "reason": "<one sentence>"}}

## Task

{brief}
