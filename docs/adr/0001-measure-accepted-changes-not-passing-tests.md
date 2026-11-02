# 1. Measure accepted changes, not passing tests

Status: accepted

## Context

The usual number for a coding agent is the share of tasks where its change passes the tests. Two
independent findings say that number overstates what a team gets:

- METR had maintainers of scikit-learn, Sphinx and pytest review 296 agent changes that passed
  SWE-bench's tests. About half would not have been merged; maintainer adoption ran about 24
  percentage points below the test pass rate.
- Comparisons of agents with equal pass rates find very different code behind them (closeness to the
  human change, unnecessary edits, review outcomes).

A team adopting an agent setup pays for review time and for what slips through review, so "passes
the tests" is the wrong unit.

## Decision

An attempt is **accepted** only when all of these hold, and the benchmark reports accepted changes
and cost per accepted change, next to the plain test pass rate:

1. the task's hidden tests pass;
2. the task state's own test suite passes, run from the original test files (an agent that edits a
   test to make it pass gets no credit for it);
3. format, lint and type checks pass;
4. no deterministic diff finding that blocks (deleted tests, removed assertions, skipped tests,
   removed invariant markers);
5. a review judge, given the repository's AGENTS.md, the brief and the diff, finds nothing a
   maintainer would block.

## Consequences

- The judge is a model and can be wrong. It is measured before it is trusted: on every task it must
  pass the reference change and reject the unmergeable variants (`aeh prove`), and the report says
  how often it did. It runs only on changes that already pass the tests, which is where its answer
  matters and keeps its cost down.
- Tasks need more than tests: a reference, mutants and unmergeable variants (tasks/WRITING_TASKS.md).
