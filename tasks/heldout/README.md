# Held-out set (target: model-router-platform)

- H01-run-approval-tenancy — bug (setup.patch): step approvals recorded on the owner connection let another workspace approve or reject a run's steps; stresses tenant isolation through `db.tenant`, 404 vs 409 semantics in the HTTP layer and `Runner.decide`.
- H02-cache-hit-charge — bug (setup.patch): cache hits billed from the pre-call estimate; stresses billing exactness (bill only the delivered call, not escalated or failed attempts), Decimal rounding and fallback/escalation paths.
- H03-stream-splice — bug (setup.patch): a stream that fails after its first chunk splices in a fallback model's answer; stresses the streaming fallback rule, the SSE error event and settlement of a cut-off stream.
- H04-monthly-budget — feature: per-workspace monthly spend budget (`PUT/GET /v1/budget`, 402 once billed spend reaches it); stresses a new table with row-level security, money as Decimal, billed vs actual vs estimated amounts and UTC month boundaries.
- H05-cancel-agent-run — feature: `POST /v1/agents/runs/{id}/cancel`; stresses agent runs that stop between steps, approvals refused after cancellation, tenancy and status-transition errors.
- H06-api-key-rotation — feature: customers create, list and revoke their own API keys; stresses secrets (hash only, never logged or listed), revocation, tenancy and a self-revocation guard.

This set was written from `tasks/WRITING_TASKS.md` only, against the target repository, without reading the harness code (`src/`, `config/`, `tests/`, `reports/`) or the dev tasks.

Caveats reported by the writer: while this set was being written, a judge call for the dev set was
running on the same machine and its prompt (a dev task's brief and reference diff) was visible in
the process list; it concerned a topic the writer had been told to avoid. Since then the harness
passes prompts on stdin, not on the command line. Error tracebacks from `aeh prove` showed a few
lines of the slot-leasing code; no harness source file was opened.
