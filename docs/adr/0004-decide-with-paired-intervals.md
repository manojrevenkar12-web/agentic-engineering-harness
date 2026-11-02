# 4. Decide with paired intervals over tasks, and an A/A noise floor

Status: accepted

## Context

A dozen tasks and a few samples per task are what a team can afford. Single runs disagree with
themselves by several tasks; published harness comparisons have been decided by fewer.

## Decision

- Tasks are the unit of resampling. Setups are compared on the same tasks (paired), with bootstrap
  intervals over tasks.
- Every setup runs at least two samples per task, and sample 1 against sample 2 of the same setup
  is reported as an A/A comparison: the size of a difference that is pure noise.
- The rule is configuration (`config/decision.yaml`): a candidate replaces the baseline if its
  accepted-rate lift has a lower bound above zero, or if no difference is measurable (lower bound
  above -10 points) and it is cheaper per accepted change. Otherwise the baseline stays.
- The chosen setup is then run once on the held-out tasks, which nobody tuned anything on.

## Consequences

- "No measurable difference" is a common and honest answer at this sample size, and the report says
  so rather than ranking setups by point estimates.
