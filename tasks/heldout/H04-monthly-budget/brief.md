# Monthly spend budget per workspace

**Requested by:** two team-plan customers whose finance teams want a hard ceiling on what the
gateway can bill them in a month.

Plans cap tokens, but customers think in euros. Let a workspace set its own monthly budget, see how
much of it is used, and have the gateway stop answering once the month's bill has reached it.

## API

- `PUT /v1/budget` with `{"monthly_limit": "25.00"}` sets the calling workspace's budget (a decimal
  amount in EUR, sent as a string or a number; it must be greater than 0, otherwise 422).
  `{"monthly_limit": null}` removes the budget.
- `GET /v1/budget` returns the workspace's budget and its use this month:

  ```json
  {"monthly_limit": "25.00000000", "spent": "3.14159265", "month": "2026-11"}
  ```

  `monthly_limit` is `null` when no budget is set. Amounts are strings with exactly 8 decimal
  places. `month` is the current calendar month in UTC, `YYYY-MM`.
- `PUT` answers with the same body as `GET`.

## Rules

- `spent` is what the workspace has been **billed** this calendar month (UTC): the sum of
  `billed_amount` over its usage rows created this month, cache hits included. It is not our provider
  cost (`actual_cost`) and not an estimate.
- When a budget is set and `spent` has reached it (`spent >= monthly_limit`),
  `POST /v1/chat/completions` is refused with **402** and the usual entitlement error body,
  `{"error": {"type": "entitlement", "message": "..."}}`, whose message mentions the monthly
  budget. A refused request calls no provider and leaves no usage row.
- A request is not refused because of its estimated cost: while `spent` is below the limit it is
  answered (even if it then takes the month past the limit).
- Budgets and spend are per workspace; one workspace's budget or spend never affects another.
