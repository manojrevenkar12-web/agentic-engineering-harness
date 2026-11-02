# agentic-engineering-harness

**How should an AI-native engineering team work with coding agents?** One agent per ticket, an agent
plus an independent reviewer, two agents racing with a selector; a small model or a large one. Teams
usually decide that from impressions. This repository decides it from measurements. Real Claude Code
agents work a backlog of tickets on a production-style AI-infrastructure codebase, each in its own
sandbox and in parallel. Every change is graded the way the maintainer who merges it would grade it.
The setups are compared on the same tasks, with the uncertainty a dozen tasks really carry.

<!-- RESULTS -->

## Why "passes the tests" is the wrong number

METR had the maintainers of scikit-learn, Sphinx and pytest review 296 agent changes that passed
SWE-bench's tests. About half would not have been merged. A team pays for that gap in review time,
or in what slips through review. So the unit here is the **accepted change**, and an attempt counts
only when all of these hold:

1. the task's **hidden tests** pass (the agent never sees them);
2. the repository's **own test suite** passes, run from the original test files, so editing a test
   to make it pass earns nothing;
3. **format, lint and type checks** pass;
4. no **diff finding** that blocks: a deleted test, removed assertions, a skipped test, a removed
   invariant marker;
5. a **review judge** finds nothing the maintainer would block. The judge reads the repository's
   AGENTS.md, the ticket and the diff, and it may read files (Read, Grep and Glob only).

Cost is reported **per accepted change**, not per attempt.

## Graders are proven before they grade

Each task ships with more than tests (see [tasks/WRITING_TASKS.md](tasks/WRITING_TASKS.md)):

- a **reference change** a maintainer would merge;
- **mutants**, the plausible wrong changes engineers and agents actually make: the boundary case,
  the second code path, the wrong error shape;
- **unmergeable changes** that pass every test and break a repository rule: a query that bypasses
  row-level security, money as float, a hard-coded model list, an unrelated price change, a deleted
  assertion.

`aeh prove` checks four things before a task may be used: the task state fails its hidden tests,
the existing suite still passes, the reference is accepted, and every mutant is caught. The
unmergeable changes measure the review step. The CI job `graders` re-proves every task against the
real target on every push.

## How it works

```
tasks/<set>/<id>/brief.md ──► task state: the pinned commit + setup.patch, exported with no git history
                                   │
         ┌─────────────────────────┼──────────────────────────┐
         ▼                         ▼                          ▼
   attempt (worktree,        attempt (worktree,         attempt ...         ◄── leased from PostgreSQL,
   own DB + Redis index)     own DB + Redis index)                              worst-case spend reserved first
         │  claude -p, least privilege, hard $ cap, prompt on stdin
         ▼
   flow: solo │ executor → independent reviewer → one revision │ two executors → selector
         ▼
   patch ──► grader (fresh copy): hidden tests · original suite · ruff/mypy · diff checks · review judge
         ▼
   PostgreSQL record (attempts, append-only spend log) ──► paired bootstrap over tasks ──► decision rule
```

- **Least privilege** ([ADR 2](docs/adr/0002-least-privilege-agent-sessions.md)). Every session gets
  a clean environment, `--restricted` file tools confined to its worktree, and an allow-list of
  commands: the project's tests, linters, type checker and read-only git. Anything else is refused
  without asking, and each refusal is recorded. `--max-budget-usd` caps each session.
- **Budget** ([ADR 3](docs/adr/0003-reserve-before-spend.md)). An attempt's worst case is reserved
  in the same transaction that leases it. A crashed worker's reservation counts as spent. Results
  are written only by the worker that holds the lease. The spend log is append-only.
- **Decisions** ([ADR 4](docs/adr/0004-decide-with-paired-intervals.md)). Setups are compared paired
  by task, with bootstrap intervals over tasks. Each setup is also compared with itself (A/A) to show
  the size of pure noise. The rule lives in `config/decision.yaml`.
- **Held-out tasks** were written blind from the guide alone, by someone who never read the harness
  or the dev tasks. They run once, and the first run is never rewritten.

## Run it

```bash
pip install -e ".[dev]"
pytest -q                                            # unit + isolation; add AEH_TEST_DATABASE_URL for the whole loop
aeh prove --set dev                                  # prove every grader (PostgreSQL with pgvector, Redis)
aeh bench --set dev --run dev-1 --setups haiku-solo,sonnet-solo --samples 3 --budget 40
aeh status --run dev-1                               # progress, spend, and the budget check
aeh regrade --run dev-1                              # grade stored patches again after a grading fix
aeh heldout --setups haiku-solo,sonnet-review --budget 15   # once
aeh report                                           # reports/results.json and docs/REPORT.md
aeh solve --issue ticket.md --setup sonnet-review    # daily use: one ticket, the adopted setup
cd web && npm ci && npm run dev                      # the dashboard
```

Configuration: `config/setups.yaml` (what is compared), `config/agent.yaml` (what agents may do),
`config/grading.yaml` (what "accepted" means), `config/decision.yaml` (when to switch),
`config/prompts/` (every prompt, versioned with the code).
