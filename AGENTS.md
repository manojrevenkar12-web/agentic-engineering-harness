# Working on this repository

## Fast feedback

- `pytest -q -m "not db"`: unit and isolation tests, seconds.
- `AEH_TEST_DATABASE_URL=postgresql://postgres@localhost:5432/aeh_test pytest -q`: adds the whole
  loop on a toy target with a fake agent (proofs, runs, budget, crash recovery), under a minute.
- `aeh prove --set dev --no-judge`: proves every dev task's grader against the real target (needs
  PostgreSQL with pgvector and Redis; minutes).
- `ruff check src tests scripts && ruff format --check src tests scripts`; `cd web && npm test`.

## Invariants (each has a test)

- **Agents never see graders.** `aeh.agent`, `aeh.flows`, `aeh.tasks`, `aeh.services` and
  `aeh.target` never import `aeh.grade` or `aeh.prove`, never name a grader directory, and the task
  state is exported without history (`tests/test_isolation.py`).
- **Least privilege.** Sessions run with a clean environment, `--restricted`, an allow-list and a
  hard spend cap (`config/agent.yaml`, ADR 2). Never widen the allow-list to make an attempt pass.
- **The budget holds at every moment.** Spend is reserved before an attempt starts, settled after,
  abandoned reservations count in full, the spend log is append-only (`tests/test_pipeline.py`, ADR 3).
- **Results are fenced by the lease.** Only the worker holding an attempt's lease can record it.
- **Graders are proven before use.** `aeh bench` refuses tasks without a proof (`reports/proofs/`).
- **Settings live in `config/`**, prompts in `config/prompts/`. Decisions come from
  `config/decision.yaml`, not from reading a table.
- **Generated files are not edited:** `reports/`, `docs/REPORT.md`.

## Held-out tasks

`tasks/heldout` was written from `tasks/WRITING_TASKS.md` by someone who did not read the harness
or the dev tasks. Never change the harness, prompts or setups to do better on it. Its first run is
`reports/heldout/first_run.json` and is never rewritten. If you study its failures, write
`regression` to `tasks/heldout/STATUS` and have someone who has not seen the code write a new set
from `tasks/WRITING_TASKS.md` only.
