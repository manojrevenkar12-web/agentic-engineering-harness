# 2. Agent sessions run with least privilege and a hard spend cap

Status: accepted

## Decision

Every session is a headless Claude Code process started with:

- a clean environment (HOME, PATH and the slot's service URLs only), so no tokens, cloud credentials
  or other projects' instructions leak in;
- `--restricted`: file tools confined to the worktree, settings files ignored;
- an allow-list of commands (`config/agent.yaml`): the project's tests, linters, type checker and
  read-only git; `--permission-mode dontAsk` refuses everything else without asking, and every
  refusal is recorded;
- `--max-budget-usd`, the session's cap, which is also what the harness reserves before starting it;
- reviewers and selectors get no edit tools; the review judge may only read files (Read, Grep, Glob).

## Why

The agent works next to the hidden tests, other attempts and the team's credentials. Isolation by
convention ("please do not read the grader") is not isolation. A cap enforced by the agent runtime is
the only way to give a hard budget for a run.

## Consequences

- An agent cannot install packages, use the network or run arbitrary scripts. Work that needs them
  is out of scope for the benchmark, which is the point: the team's daily setup has the same limits.
- Denied actions are a metric: a setup that keeps trying forbidden commands wastes turns.
