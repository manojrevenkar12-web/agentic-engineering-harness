Some enterprise customers must keep their prompts on the open-weight models we serve on our own
GPUs (data residency). Add a request option for them.

- New option in the request's `mrp` object: `open_weight_only` (boolean, default false).
- When it is true, only models marked `open_weight` in the catalogue may serve the request. With
  `model: "auto"` the router chooses only among open-weight models, including fallbacks and any
  cheaper model it tries first.
- When it is true and the caller names a specific model that is not open-weight, reject the request
  with HTTP 422 and an error message that says the model is not open-weight.
- When no open-weight model can take the request (for example, it is longer than their context),
  return the usual no-route error (HTTP 422, `no_route`).
- Requests without the option behave exactly as today.
