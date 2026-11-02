Customers choosing a model by hand want to see what it costs. Extend `GET /v1/models` so that
every catalogue model in the list also has:

- `context`: its context window in tokens (integer),
- `price_in` and `price_out`: our price in EUR per million input / output tokens, exactly as in the
  catalogue,
- `fine_tuned_for`: the task it is fine-tuned for, only on models that have one.

The `auto` entry stays as it is.
