# Another workspace can approve or reject our agent run's steps

**Reported by:** security review, severity high

A customer pasted an agent run id into a public support thread. Shortly afterwards the run's
pending `gmail.send` step showed `decided_by: "integration-bot"`, a user name that belongs to a
different customer. We reproduced it: with workspace B's API key,

```
POST /v1/agents/runs/<run id of workspace A>/steps/<step>/approve
X-MRP-User: integration-bot
```

returns 200 and records the approval on workspace A's step (the same for `/reject`). Once a worker
picks the run up again, A's email goes out on B's say-so.

## Expected

- Deciding a step of a run that does not belong to the caller's workspace returns **404** with
  detail `no such run` (the same answer `GET /v1/agents/runs/{run_id}` gives) and changes nothing:
  the step stays `waiting_approval` with no `decided_by`, and the run's status is unchanged.
- A run id that does not exist at all also returns **404** `no such run`.
- For the caller's own run, nothing changes: deciding a step that is waiting for approval returns
  200 as today, and deciding a step that has nothing pending still returns **409**.
- `Runner.decide(workspace_id, run_id, ...)` is also called outside the HTTP handler; called with a
  workspace that does not own the run, it must raise and record nothing.
