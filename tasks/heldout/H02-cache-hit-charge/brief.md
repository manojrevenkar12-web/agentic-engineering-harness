# Cached answers are billed from the estimate, not from what the original call cost

**Reported by:** finance, during the October invoice review

Our pricing page says a request answered from the cache costs 10% of what the original answer
cost (the catalogue's `cache.cached_answer_charge`), plus the plan's markup. Finance recomputed
October's cache-hit lines from the ledger and they do not match: the amounts follow the
`x-mrp-estimated-cost` of the *original* request (our pre-call estimate from token guesses), not the
provider-reported cost of the call that produced the answer. For short summaries the estimate is
several times the real cost, so customers were overcharged on every cache hit.

## Expected

For a request answered from the cache, exact or semantic:

- `billed_amount` (and the `x-mrp-billed` response header) is
  `cost × cached_answer_charge × (1 + plan markup)`, rounded half up to 8 decimal places, where
  `cost` is the **actual** cost of the provider call that produced the cached answer (the call
  marked `delivered` in `mrp.provider_calls`).
- Only that call counts. Calls that failed, and a cheap first try whose answer failed the check and
  was escalated, are our cost and never part of what a cache hit is billed from.
- Unchanged: the hit's `actual_cost` is 0 and its `avoided_cost_est` is the estimate of the request
  that was served from the cache.

Answers already in the cache when the fix ships do not need repairing.
