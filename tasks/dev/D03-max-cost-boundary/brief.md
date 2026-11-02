Bug: a request whose cheapest suitable model costs exactly the effective cost limit (the plan's
`max_request_cost`, or the request's `mrp.max_cost` if lower) is refused with `no_route`, although
the limit is documented as the most a request may cost. A request that costs exactly the limit must
be allowed; one that costs more than the limit must still be refused.
