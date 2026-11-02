A typo in `models.yaml` (a negative price, a context of 0, a quality target of 90 instead of 0.90)
currently loads fine and only shows up later as strange routing. Make `mrp.catalog.load()` refuse a
broken catalogue with a clear error instead.

- Raise `mrp.catalog.CatalogError` (a subclass of `ValueError`) whose message names the offending
  model, plan or target.
- Invalid: a negative `price_in` or `price_out`; a `context` that is not a positive integer; a
  quality target outside (0, 1]; a plan with a negative `max_request_cost` or `markup`; a
  `cached_answer_charge` outside [0, 1].
- The shipped catalogue must keep loading.
