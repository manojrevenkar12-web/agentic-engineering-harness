# Cancel an agent run

**Requested by:** a team-plan customer whose on-call engineer started a run with the wrong goal and
had no way to stop it before it posted to Slack and emailed a partner.

Today a run can only end by succeeding, failing, running out of budget or having a step rejected.
Add a way to cancel it.

## API

`POST /v1/agents/runs/{run_id}/cancel`

- For a run of the caller's workspace whose status is `queued`, `running` or `waiting_approval`:
  sets the run's status to `cancelled` and returns **200** with
  `{"run_id": "<run id>", "status": "cancelled"}`. `GET /v1/agents/runs/{run_id}` then shows
  `"status": "cancelled"`.
- For a run that has already ended (`succeeded`, `failed`, `budget_exhausted`, `rejected` or
  `cancelled`): **409**, and the run is left as it is.
- For a run that does not exist in the caller's workspace (including another workspace's run):
  **404** with detail `no such run`, and nothing changes.

## What cancelling means

- A cancelled run never starts another step, whether it was queued, waiting for approval or being
  executed by a worker at that moment. A step a worker is already executing finishes and is
  checkpointed as usual; no later step (model or tool) starts, so no further provider call or tool
  effect happens.
- When the worker notices the cancellation, `Runner.run` returns `"cancelled"` and the run stays
  `cancelled`. Running a run that was already cancelled returns `"not_runnable"`, as for any run
  that cannot be leased.
- Approving or rejecting a step of a cancelled run is refused with **409** (the step keeps its
  status and the run stays `cancelled`).
